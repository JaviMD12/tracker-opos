"""Scraper de boletines oficiales (BOE y BOJA) para el Tablon de Plazas Premium.

Descarga los canales RSS de "Oposiciones y concursos" de ambos boletines,
filtra por palabras clave de emergencias/bomberos, y por cada entrada nueva
pide a gpt-4o-mini que extraiga los datos estructurados de la convocatoria.
Los resultados se guardan en la tabla `convocatorias`.

Pensado para ejecutarse como tarea periodica (ver el cron de APScheduler en
app/main.py), no como parte de una peticion HTTP: los errores se registran
por consola y se salta a la siguiente entrada, nunca se relanzan, para que un
fallo puntual (un feed caido, una respuesta rara de OpenAI) no tumbe el resto
del lote ni el proceso del servidor.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAIError

import feedparser

from app.database import SessionLocal
from app.models.convocatoria import Convocatoria

# URLs de RSS verificadas manualmente (feeds reales, en produccion a fecha de
# escribir esto): BOE "Oposiciones" y BOJA "2.2. Oposiciones y concursos".
FEEDS_BOLETINES = [
    "https://www.boe.es/rss/canal_per.php?l=p&c=140",
    "https://www.juntadeandalucia.es/boja/distribucion/s53.xml",
]

PALABRAS_CLAVE = [
    "bombero",
    "bomberos",
    "consorcio",
    "extincion",
    "extinción",
    "salvamento",
    "proteccion civil",
    "protección civil",
]

MODELO_EXTRACCION = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "Eres un extractor de datos de boletines oficiales españoles. Analiza este "
    "texto y devuelve ÚNICAMENTE un JSON válido con esta estructura exacta: "
    '{"titulo_plaza": string, "organismo_localidad": string, "plazo_dias": int, '
    '"requisitos_minimos": string}. Si el texto no menciona explícitamente una '
    'convocatoria de empleo u oposición, devuelve exactamente {"error": "no es convocatoria"}.'
)


def _contiene_palabra_clave(texto: str) -> bool:
    texto_normalizado = texto.lower()
    return any(palabra in texto_normalizado for palabra in PALABRAS_CLAVE)


def _obtener_entradas_filtradas() -> list:
    """Descarga los feeds configurados y devuelve las entradas que mencionan
    emergencias/bomberos en su titulo o descripcion."""
    entradas_filtradas = []
    for url_feed in FEEDS_BOLETINES:
        feed = feedparser.parse(url_feed)
        for entrada in feed.entries:
            texto = f"{entrada.get('title', '')} {entrada.get('summary', '')}"
            if _contiene_palabra_clave(texto):
                entradas_filtradas.append(entrada)
    return entradas_filtradas


def _extraer_datos_convocatoria(texto: str) -> dict | None:
    """Llama a gpt-4o-mini para estructurar el texto de una entrada.

    Devuelve None si el modelo determina que no es una convocatoria real.
    """
    llm = ChatOpenAI(
        model=MODELO_EXTRACCION,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    respuesta = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=texto)]
    )
    datos = json.loads(respuesta.content)

    if "error" in datos:
        return None
    return datos


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

            texto = f"{entrada.get('title', '')}\n{entrada.get('summary', '')}"

            try:
                datos = _extraer_datos_convocatoria(texto)
            except (OpenAIError, json.JSONDecodeError) as exc:
                print(f"[scraper_boletines] Fallo al procesar '{url_origen}': {exc}")
                continue

            if datos is None:
                continue

            plazo_dias = datos.get("plazo_dias")
            convocatoria = Convocatoria(
                titulo_plaza=str(datos.get("titulo_plaza", ""))[:500],
                organismo_localidad=str(datos.get("organismo_localidad", ""))[:500],
                plazo_dias=plazo_dias if isinstance(plazo_dias, int) else None,
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
