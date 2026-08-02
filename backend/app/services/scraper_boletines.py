"""Scraper de boletines oficiales (BOE y BOJA) para el Tablon de Plazas Premium.

Descarga los canales RSS de "Oposiciones y concursos" de ambos boletines,
filtra por palabras clave de emergencias/bomberos, y por cada entrada nueva
pide a Gemini que extraiga los datos estructurados de la convocatoria.
Los resultados se guardan en la tabla `convocatorias`.

Pensado para ejecutarse como tarea periodica (ver el cron de APScheduler en
app/main.py), no como parte de una peticion HTTP: los errores se registran
por consola y se salta a la siguiente entrada, nunca se relanzan, para que un
fallo puntual (un feed caido, una respuesta rara de Gemini) no tumbe el resto
del lote ni el proceso del servidor.
"""

import json
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from google.genai.errors import APIError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

import feedparser

from app.database import SessionLocal
from app.models.convocatoria import Convocatoria

# URLs de RSS verificadas manualmente (feeds reales, en produccion a fecha de
# escribir esto): BOE "Oposiciones" y BOJA "2.2. Oposiciones y concursos".
FEEDS_BOLETINES = [
    "https://www.boe.es/rss/canal_per.php?l=p&c=140",
    "https://www.juntadeandalucia.es/boja/distribucion/s53.xml",
]

# "consorcio" se elimino a proposito: por si sola metia ruido de consorcios
# de aguas, culturales, etc. que no tienen nada que ver con emergencias.
PALABRAS_CLAVE = [
    "bombero",
    "bomberos",
    "extincion de incendios",
    "extinción de incendios",
    "salvamento",
    "proteccion civil",
    "protección civil",
]

# Lista negra: resoluciones conjuntas de ayuntamientos que agrupan varias
# categorias (policia, guardia civil...) junto con bomberos. Se descartan
# aunque contengan una palabra clave valida, para que el Tutor IA nunca
# reciba una plaza que en realidad no es de emergencias.
PALABRAS_PROHIBIDAS = ["policia", "policía", "guardia civil"]

MODELO_EXTRACCION = "gemini-2.5-flash"
CARACTERES_MAXIMOS_TEXTO_COMPLETO = 15_000
TIMEOUT_DESCARGA_SEGUNDOS = 15
CABECERAS_DESCARGA = {"User-Agent": "Mozilla/5.0 (compatible; TrackerOposicionesBot/1.0)"}

SYSTEM_PROMPT = (
    "Eres un extractor de datos de boletines oficiales españoles. Analiza este "
    "texto y devuelve ÚNICAMENTE un JSON válido con esta estructura exacta: "
    '{"titulo_plaza": string, "organismo_localidad": string, "plazo_dias": int, '
    '"plazo_tipo": "habiles" | "naturales", "requisitos_minimos": string, '
    '"fecha_publicacion_boletin": string | null}. '
    'El campo "plazo_tipo" indica si el plazo esta expresado en dias habiles '
    "(excluyen sabados y domingos) o dias naturales (todos los dias) segun el "
    "propio texto -- si no lo especifica explicitamente, usa \"naturales\". "
    'El campo "fecha_publicacion_boletin" es la fecha REAL en la que el '
    'boletin oficial publico esta resolucion, en formato "AAAA-MM-DD". '
    'Busca especificamente una frase tipo "Publicado en: BOE num. X, de D de '
    'mes de AAAA" (o equivalente en BOJA/BOP) -- esa es la fecha de '
    'PUBLICACION, la que cuenta para calcular el plazo. NO confundas esto '
    'con la fecha de la "Resolucion de D de mes de AAAA" que suele aparecer '
    'tambien: esa es cuando se FIRMO el acto administrativo, normalmente '
    'unos dias ANTES de publicarse, y no es la fecha que abre el plazo. Si '
    'no aparece explicitamente la fecha de publicacion en el texto, '
    'devuelve null -- no la infieras ni uses la fecha de la resolucion como '
    'sustituto. '
    'Si el texto no menciona explícitamente una convocatoria de empleo u '
    'oposición, devuelve exactamente {"error": "no es convocatoria"}.'
)


def _contiene_palabra_clave(texto: str) -> bool:
    texto_normalizado = texto.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE)


def _contiene_palabra_prohibida(texto: str) -> bool:
    texto_normalizado = texto.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_PROHIBIDAS)


def _obtener_entradas_filtradas() -> list:
    """Descarga los feeds configurados y devuelve las entradas que mencionan
    emergencias/bomberos en su titulo o descripcion, descartando de raiz las
    resoluciones conjuntas que tambien incluyen policia/guardia civil."""
    entradas_filtradas = []
    for url_feed in FEEDS_BOLETINES:
        feed = feedparser.parse(url_feed)
        for entrada in feed.entries:
            texto = f"{entrada.get('title', '')} {entrada.get('summary', '')}"

            if _contiene_palabra_prohibida(texto):
                continue

            if _contiene_palabra_clave(texto):
                entradas_filtradas.append(entrada)
    return entradas_filtradas


def _obtener_texto_completo(url: str) -> str | None:
    """Descarga la pagina de la noticia y concatena el texto de sus <p>,
    <dd> y <dt>, recortado a CARACTERES_MAXIMOS_TEXTO_COMPLETO.

    El RSS solo trae un resumen de una o dos frases, sin plazos ni
    requisitos; esos datos viven en el cuerpo de la resolucion completa.
    <dd>/<dt> se añadieron porque el BOE (y otros boletines con el mismo
    patron) publican su ficha de metadatos -- "Publicado en: BOE num. 127,
    de 25 de mayo de 2026..." -- en una lista de definicion, no en un <p>;
    sin esto, _extraer_datos_convocatoria() nunca veia la fecha real de
    publicacion en el texto (solo <p> no la contenia), y el calculo de
    fecha_limite quedaba a merced de los metadatos del RSS (ver
    _parsear_fecha_boletin). Devuelve None si la descarga falla (red caida,
    pagina movida...), para que el llamador pueda decidir un texto de
    respaldo en vez de abortar.
    """
    try:
        respuesta = requests.get(
            url, timeout=TIMEOUT_DESCARGA_SEGUNDOS, headers=CABECERAS_DESCARGA
        )
        respuesta.raise_for_status()
    except requests.RequestException as exc:
        print(f"[scraper_boletines] No se pudo descargar '{url}': {exc}")
        return None

    soup = BeautifulSoup(respuesta.text, "html.parser")
    # Los metadatos (<dd>/<dt>) van primero, antes que los <p> del cuerpo:
    # en paginas muy largas (anexos, requisitos extensos) el recorte a
    # CARACTERES_MAXIMOS_TEXTO_COMPLETO podria cortar el texto antes de
    # llegar a la fecha real de publicacion si fuera al final. Los <dd>/<dt>
    # de una ficha de metadatos son un bloque corto, asi que anteponerlos no
    # les quita espacio de forma apreciable al cuerpo real de la resolucion.
    metadatos = [el.get_text(strip=True) for el in soup.find_all(["dd", "dt"])]
    parrafos = [el.get_text(strip=True) for el in soup.find_all("p")]
    fragmentos = metadatos + parrafos
    texto_completo = "\n".join(fragmento for fragmento in fragmentos if fragmento)
    if not texto_completo:
        print(f"[scraper_boletines] '{url}' no tiene texto en <p>/<dd>/<dt>, se usara el resumen del RSS.")
    return texto_completo[:CARACTERES_MAXIMOS_TEXTO_COMPLETO]


def _extraer_datos_convocatoria(texto: str) -> dict | None:
    """Llama a Gemini para estructurar el texto de una entrada.

    Devuelve None si el modelo determina que no es una convocatoria real.
    """
    llm = ChatGoogleGenerativeAI(
        model=MODELO_EXTRACCION,
        temperature=0,
        response_mime_type="application/json",
    )
    respuesta = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=texto)]
    )
    datos = json.loads(respuesta.content)

    # response_mime_type="application/json" solo garantiza JSON sintacticamente
    # valido, no que tenga forma de objeto -- Gemini podria en teoria devolver
    # una lista, un numero o null. Sin este chequeo, "error" in datos revienta
    # con TypeError si datos es None, y el resto del pipeline revienta con
    # AttributeError al llamar datos.get(...) si es una lista o un string.
    if not isinstance(datos, dict) or "error" in datos:
        return None
    return datos


def _fecha_publicacion_entrada(entrada) -> datetime | None:
    """Fecha real de publicacion de la entrada del feed (BOE trae
    'published_parsed', BOJA solo 'updated_parsed') -- no la fecha en la que
    el scraper la procesa. El cron corre una vez al dia (ver main.py), asi
    que una entrada puede tardar hasta 24h en recogerse: calcular el plazo
    desde el momento del scraping en vez de desde la publicacion real hacia
    que la convocatoria pareciera durar mas de lo que dura de verdad, y se
    quedara en el tablon dias despues de haber vencido.

    Devuelve None (no "ahora") cuando el feed no trae ninguna fecha. Asumir
    "ahora" como publicacion siempre calcula un fecha_limite en el futuro
    por construccion (hoy + plazo_dias siempre es "mañana" o mas tarde),
    lo que anularia por completo la red de seguridad de
    ejecutar_scraping_boletines() (que solo descarta plazos YA vencidos):
    una convocatoria realmente antigua sin metadatos de fecha se colaria
    disfrazada de recien publicada, exactamente el bug que se acaba de
    corregir para el caso de Huelva, pero por una via distinta. El llamador
    decide que hacer si tampoco hay fecha extraida del texto (ver
    _parsear_fecha_boletin): lo correcto es descartar la entrada, no
    adivinar.
    """
    parsed = entrada.get("published_parsed") or entrada.get("updated_parsed")
    if parsed is None:
        return None
    # feedparser normaliza *_parsed a UTC independientemente del offset
    # original del feed.
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _parsear_fecha_boletin(valor) -> datetime | None:
    """Fecha de publicacion que el modelo extrajo directamente del texto de
    la resolucion (ver "fecha_publicacion_boletin" en SYSTEM_PROMPT), con
    comprobaciones de sensatez antes de confiar en ella.

    Es mas fiable que _fecha_publicacion_entrada() (metadatos del RSS): el
    texto oficial declara su propia fecha de publicacion (p.ej. "BOE num.
    127, de 25 de mayo de 2026"), mientras que el campo "updated_parsed" del
    RSS a veces refleja cuando el feed toco/reactivo la entrada, no cuando se
    publico de verdad -- eso fue justo lo que causo que una convocatoria de
    bomberos de Huelva con plazo de solicitudes cerrado desde junio
    apareciera en el tablon con un plazo limite calculado para agosto (la
    fecha del RSS estaba casi dos meses por delante de la fecha real del
    BOE). Devuelve None (y el llamador cae de vuelta al RSS) si el valor no
    es parseable, es futuro, o es tan antiguo que huele a alucinacion del
    modelo en vez de una fecha real leida del texto.
    """
    if not valor or not isinstance(valor, str):
        return None
    try:
        fecha = datetime.strptime(valor, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    ahora = datetime.now(timezone.utc)
    if fecha > ahora + timedelta(days=1) or fecha < ahora - timedelta(days=3 * 365):
        return None
    return fecha


def _normalizar_plazo_dias(valor) -> int | None:
    """Normaliza "plazo_dias" a un entero positivo o None.

    El prompt pide un int, pero Gemini a veces lo devuelve como float
    (20.0) o como string numerico ("20"). Antes se rechazaba con un
    isinstance(x, int) estricto, y eso tenia un efecto en cascada peor de lo
    que parece: plazo_dias_valido=None hacia que fecha_limite_calculada
    tambien quedara en None, y la red de seguridad de plazos vencidos (ver
    ejecutar_scraping_boletines) solo actua cuando fecha_limite_calculada
    es verdadero -- asi que una convocatoria YA vencida con un plazo_dias
    mal tipado se colaba sin fecha_limite en vez de descartarse.

    bool se excluye a proposito: en Python bool es subclase de int, y
    "plazo_dias": true pasaria isinstance(x, int) sin ser un plazo real.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor if valor > 0 else None
    if isinstance(valor, float) and valor.is_integer():
        return int(valor) if valor > 0 else None
    if isinstance(valor, str):
        try:
            entero = int(valor.strip())
        except ValueError:
            return None
        return entero if entero > 0 else None
    return None


def _dias_habiles_a_naturales(dias_habiles: int, fecha_inicio: datetime) -> int:
    """Convierte un plazo en dias habiles a dias naturales equivalentes,
    contando desde fecha_inicio y saltando sabados y domingos.

    No tiene en cuenta festivos nacionales/autonomicos (necesitaria un
    calendario laboral por comunidad autonoma) -- el plazo real puede ser
    un poco mas corto si hay festivos de por medio, pero es mucho mas
    preciso que tratar "dias habiles" como si fueran dias naturales.
    """
    dias_naturales = 0
    dias_habiles_contados = 0
    fecha = fecha_inicio
    while dias_habiles_contados < dias_habiles:
        fecha += timedelta(days=1)
        dias_naturales += 1
        if fecha.weekday() < 5:  # 0-4 = lunes a viernes
            dias_habiles_contados += 1
    return dias_naturales


def ejecutar_scraping_boletines() -> None:
    """Punto de entrada del cron diario: descarga, filtra, extrae y guarda."""
    entradas = _obtener_entradas_filtradas()
    db = SessionLocal()
    nuevas = 0

    try:
        for entrada in entradas:
            url_origen = entrada.get("link")
            if not url_origen:
                continue

            ya_existe = (
                db.query(Convocatoria)
                .filter(Convocatoria.url_origen == url_origen)
                .first()
            )
            if ya_existe:
                continue

            texto_resumen = f"{entrada.get('title', '')}\n{entrada.get('summary', '')}"
            texto_completo = _obtener_texto_completo(url_origen)
            texto = texto_completo if texto_completo else texto_resumen

            try:
                datos = _extraer_datos_convocatoria(texto)
            except (APIError, json.JSONDecodeError) as exc:
                print(f"[scraper_boletines] Fallo al procesar '{url_origen}': {exc}")
                continue

            if datos is None:
                continue

            # Todo lo demas (validacion de campos, calculo de fechas, guardado
            # en BD) va dentro de este try/except Exception como red de
            # seguridad final: antes, cualquier excepcion no prevista aqui
            # (un IntegrityError de carrera entre workers de gunicorn -- cada
            # uno corre su propio scheduler, ver app/main.py --, o cualquier
            # otra cosa no anticipada) abortaba ejecutar_scraping_boletines()
            # entero. Y como la fila nunca llegaba a comprometerse, ni
            # siquiera quedaba deduplicada por url_origen, asi que la misma
            # entrada podia volver a reventar la ejecucion del dia siguiente,
            # bloqueando indefinidamente todo lo que viniera despues en el
            # feed. Esto es lo que el docstring del modulo ya prometia
            # ("nunca se relanzan") pero no cumplia mas alla de la llamada al
            # LLM.
            try:
                titulo_plaza = datos.get("titulo_plaza")
                organismo_localidad = datos.get("organismo_localidad")
                # .get(clave, "") solo usa el default si falta la clave; si
                # Gemini la incluye con JSON null, .get devuelve None, y
                # str(None) guardaria el texto literal "None" como titulo o
                # organismo -- una fila con pinta valida pero mal.
                # titulo_plaza/organismo_localidad son NOT NULL en el modelo
                # (ver app/models/convocatoria.py), asi que si no son un
                # string real se descarta la entrada en vez de guardar un
                # placeholder.
                if not isinstance(titulo_plaza, str) or not titulo_plaza.strip():
                    print(f"[scraper_boletines] '{url_origen}' descartada: sin titulo_plaza valido.")
                    continue
                if not isinstance(organismo_localidad, str) or not organismo_localidad.strip():
                    print(f"[scraper_boletines] '{url_origen}' descartada: sin organismo_localidad valido.")
                    continue

                plazo_dias_valido = _normalizar_plazo_dias(datos.get("plazo_dias"))

                # fecha_limite se calcula una sola vez aqui, a partir de la fecha
                # REAL de publicacion en el boletin, para que el conteo de dias
                # restantes sea real y vaya bajando dia a dia (ver
                # Convocatoria.dias_restantes) en vez de sobreestimar cuanto
                # plazo queda. Se prioriza la fecha que el propio texto declara
                # (_parsear_fecha_boletin) sobre los metadatos del RSS
                # (_fecha_publicacion_entrada), que pueden ir muy por delante de
                # la publicacion real -- ver el docstring de _parsear_fecha_boletin.
                fecha_publicacion_real = _parsear_fecha_boletin(
                    datos.get("fecha_publicacion_boletin")
                ) or _fecha_publicacion_entrada(entrada)

                # Si ninguna de las dos fuentes dio una fecha fiable, no hay
                # base real para calcular un plazo -- mejor descartar la
                # entrada que asumir "ahora" (ver docstring de
                # _fecha_publicacion_entrada: eso fue justo lo que hizo que
                # una convocatoria vencida pareciera vigente).
                if fecha_publicacion_real is None:
                    print(
                        f"[scraper_boletines] '{url_origen}' descartada: no se pudo "
                        "determinar una fecha de publicacion fiable (ni en el "
                        "texto ni en los metadatos del RSS)."
                    )
                    continue

                dias_naturales_equivalentes = None
                if plazo_dias_valido:
                    if datos.get("plazo_tipo") == "habiles":
                        dias_naturales_equivalentes = _dias_habiles_a_naturales(
                            plazo_dias_valido, fecha_publicacion_real
                        )
                    else:
                        dias_naturales_equivalentes = plazo_dias_valido

                fecha_limite_calculada = (
                    fecha_publicacion_real + timedelta(days=dias_naturales_equivalentes)
                    if dias_naturales_equivalentes
                    else None
                )

                # Red de seguridad: si con la mejor fecha de publicacion
                # disponible el plazo ya vencio, no tiene sentido mostrarle al
                # usuario una convocatoria en la que ya no puede presentar
                # solicitud -- se descarta aqui en vez de guardarla y confiar en
                # el filtro de lectura de GET /api/convocatorias (ver
                # routers/convocatorias.py), que solo protege el listado pero
                # deja la fila muerta acumulandose en la tabla.
                if fecha_limite_calculada and fecha_limite_calculada < datetime.now(timezone.utc):
                    print(
                        f"[scraper_boletines] '{url_origen}' descartada: el plazo "
                        f"ya vencio ({fecha_limite_calculada.date()})."
                    )
                    continue

                requisitos_minimos = datos.get("requisitos_minimos")
                if not isinstance(requisitos_minimos, str):
                    requisitos_minimos = None

                convocatoria = Convocatoria(
                    titulo_plaza=titulo_plaza.strip()[:500],
                    organismo_localidad=organismo_localidad.strip()[:500],
                    plazo_dias=plazo_dias_valido,
                    fecha_publicacion=fecha_publicacion_real,
                    fecha_limite=fecha_limite_calculada,
                    requisitos_minimos=requisitos_minimos,
                    url_origen=url_origen,
                )
                db.add(convocatoria)
                db.commit()
                nuevas += 1
            except Exception as exc:
                db.rollback()
                print(f"[scraper_boletines] Error inesperado procesando '{url_origen}': {exc}")
                continue

        print(
            f"[scraper_boletines] Ejecucion completada: {nuevas} convocatorias "
            f"nuevas de {len(entradas)} entradas candidatas."
        )
    finally:
        db.close()
