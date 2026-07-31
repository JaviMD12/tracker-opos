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
    '"plazo_tipo": "habiles" | "naturales", "requisitos_minimos": string}. '
    'El campo "plazo_tipo" indica si el plazo esta expresado en dias habiles '
    "(excluyen sabados y domingos) o dias naturales (todos los dias) segun el "
    "propio texto -- si no lo especifica explicitamente, usa \"naturales\". "
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
    """Descarga la pagina de la noticia y concatena el texto de todos sus
    <p>, recortado a CARACTERES_MAXIMOS_TEXTO_COMPLETO.

    El RSS solo trae un resumen de una o dos frases, sin plazos ni
    requisitos; esos datos viven en el cuerpo de la resolucion completa.
    Devuelve None si la descarga falla (red caida, pagina movida...), para
    que el llamador pueda decidir un texto de respaldo en vez de abortar.
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
    parrafos = [p.get_text(strip=True) for p in soup.find_all("p")]
    texto_completo = "\n".join(parrafo for parrafo in parrafos if parrafo)
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

    if "error" in datos:
        return None
    return datos


def _fecha_publicacion_entrada(entrada) -> datetime:
    """Fecha real de publicacion de la entrada del feed (BOE trae
    'published_parsed', BOJA solo 'updated_parsed') -- no la fecha en la que
    el scraper la procesa. El cron corre una vez al dia (ver main.py), asi
    que una entrada puede tardar hasta 24h en recogerse: calcular el plazo
    desde el momento del scraping en vez de desde la publicacion real hacia
    que la convocatoria pareciera durar mas de lo que dura de verdad, y se
    quedara en el tablon dias despues de haber vencido.
    """
    parsed = entrada.get("published_parsed") or entrada.get("updated_parsed")
    if parsed is None:
        return datetime.now(timezone.utc)
    # feedparser normaliza *_parsed a UTC independientemente del offset
    # original del feed.
    return datetime(*parsed[:6], tzinfo=timezone.utc)


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

            plazo_dias = datos.get("plazo_dias")
            plazo_dias_valido = (
                plazo_dias if isinstance(plazo_dias, int) and plazo_dias > 0 else None
            )

            # fecha_limite se calcula una sola vez aqui, a partir de la fecha
            # REAL de publicacion en el boletin (no de "ahora", el momento en
            # que el cron diario procesa la entrada -- puede ir hasta 24h por
            # detras de la publicacion real), para que el conteo de dias
            # restantes sea real y vaya bajando dia a dia (ver
            # Convocatoria.dias_restantes) en vez de sobreestimar cuanto
            # plazo queda.
            fecha_publicacion_real = _fecha_publicacion_entrada(entrada)

            dias_naturales_equivalentes = None
            if plazo_dias_valido:
                if datos.get("plazo_tipo") == "habiles":
                    dias_naturales_equivalentes = _dias_habiles_a_naturales(
                        plazo_dias_valido, fecha_publicacion_real
                    )
                else:
                    dias_naturales_equivalentes = plazo_dias_valido

            convocatoria = Convocatoria(
                titulo_plaza=str(datos.get("titulo_plaza", ""))[:500],
                organismo_localidad=str(datos.get("organismo_localidad", ""))[:500],
                plazo_dias=plazo_dias_valido,
                fecha_publicacion=fecha_publicacion_real,
                fecha_limite=(
                    fecha_publicacion_real + timedelta(days=dias_naturales_equivalentes)
                    if dias_naturales_equivalentes
                    else None
                ),
                requisitos_minimos=datos.get("requisitos_minimos"),
                url_origen=url_origen,
            )
            db.add(convocatoria)
            db.commit()
            nuevas += 1

        print(
            f"[scraper_boletines] Ejecucion completada: {nuevas} convocatorias "
            f"nuevas de {len(entradas)} entradas candidatas."
        )
    finally:
        db.close()
