"""Script offline para precargar el Banco de Preguntas de los Simulacros IA.

No depende de FastAPI ni de que el servidor este arrancado: se conecta
directamente a la base de datos (SQLite local o Postgres, segun DATABASE_URL)
y llama a Gemini una sola vez por lote, en vez de en cada peticion del
frontend. Uso:

    cd backend
    python generar_banco.py

Pide por consola el tema y la cantidad de preguntas a generar.

Cada lote se genera con RAG contra el mismo vectorstore que usa el Tutor IA
(app/services/ai_tutor.py, indexado desde app/conocimiento/): se recuperan
fragmentos reales del temario para el tema+enfoque de ese lote y se le piden
al modelo preguntas basadas en ellos, en vez de en su conocimiento general.
Si backend/chroma_db_data/ no existe todavia, la primera llamada lo
construye sobre la marcha (1-2 min extra, ver ai_tutor.py).
"""

import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from google.genai.errors import APIError  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.pregunta_test import PreguntaTest  # noqa: E402
from app.services.ai_tutor import _obtener_vectorstore  # noqa: E402

MODELO_CHAT = "gemini-2.5-flash"
FRAGMENTOS_A_RECUPERAR = 8

# Pedir de golpe muchas preguntas choca con el limite de tokens de salida de
# OpenAI (el modelo simplemente devuelve menos de las pedidas, sin avisar).
# Por eso las cantidades grandes se trocean en varias llamadas mas pequeñas.
TAMANO_LOTE = 20

TEMAS_CONOCIDOS = [
    "Legislacion",
    "General",
    "Rescate",
    "Sanitario",
    "Incendio",
    "Equipos de Intervencion",
]

# Se rota un enfoque distinto por lote (ver generar_preguntas_openai) para
# que lotes sucesivos del mismo tema no conviertan siempre en las mismas
# 3-4 preguntas "obvias" de manual -- sin esto, con 300 preguntas pedidas en
# 15 lotes identicos, OpenAI tiende a repetir o parafrasear las mismas ideas.
ENFOQUES_ROTATORIOS = [
    "definiciones y conceptos fundamentales",
    "cifras, parametros tecnicos y datos numericos exactos",
    "excepciones a la norma general y casos limite",
    "procedimientos y el orden correcto de los pasos a seguir",
    "matices que distinguen entre si conceptos parecidos",
    "detalles tecnicos infrecuentes y aspectos poco evidentes del temario",
]

SYSTEM_PROMPT = (
    "Eres un tribunal oficial de oposiciones de bomberos y emergencias. Tu "
    "objetivo es generar preguntas de examen tipo test a partir del CONTEXTO "
    "que se te proporciona en cada peticion (fragmentos reales extraidos del "
    "temario oficial) -- no uses conocimiento general propio ni inventes "
    "datos, cifras o articulos que no aparezcan en ese contexto; si el "
    "contexto no da para una pregunta con un dato concreto, prioriza otro "
    "concepto que si aparezca explicitamente en el. Usa vocabulario tecnico "
    "preciso (por ejemplo, usa 'hidrante' en lugar de terminos genericos "
    "como 'aparato'). Cada pregunta debe tener exactamente 4 opciones, con "
    "una unica respuesta correcta y una justificacion breve de por que lo "
    "es. Devuelve UNICAMENTE un objeto JSON valido con esta estructura "
    'exacta: {"preguntas": [{"enunciado": "texto", '
    '"opciones": ["A", "B", "C", "D"], "respuesta_correcta": 0, '
    '"justificacion": "por que es correcta"}]}. El campo "respuesta_correcta" '
    "es el indice (0 a 3) de la opcion valida dentro de \"opciones\".\n\n"
    "VARIEDAD (muy importante, esto se genera en muchos lotes independientes "
    "que no deben solaparse entre si): evita las preguntas mas obvias sobre "
    "el tema, las 3-4 que cualquiera haria primero -- explora en su lugar "
    "aspectos concretos, casos particulares y detalles tecnicos especificos "
    "presentes en el contexto. No repitas preguntas entre si dentro del "
    "mismo lote, ni reformules la misma idea cambiando solo las palabras."
)


def _recuperar_contexto(vectorstore, tema: str, enfoque: str) -> str:
    """Fragmentos reales del temario (mismo indice que el Tutor IA) mas
    afines a este tema+enfoque, para anclar el lote a documentos reales en
    vez de al conocimiento general del modelo."""
    fragmentos = vectorstore.similarity_search(
        f"{tema}: {enfoque}", k=FRAGMENTOS_A_RECUPERAR
    )
    return "\n\n---\n\n".join(fragmento.page_content for fragmento in fragmentos)


def generar_preguntas_gemini(
    cliente: genai.Client,
    vectorstore,
    tema: str,
    cantidad: int,
    numero_lote: int,
    enunciados_existentes: list[str],
) -> list[dict]:
    enfoque = ENFOQUES_ROTATORIOS[(numero_lote - 1) % len(ENFOQUES_ROTATORIOS)]
    identificador_variedad = random.randint(100_000, 999_999)
    contexto = _recuperar_contexto(vectorstore, tema, enfoque)

    instrucciones = (
        f"CONTEXTO (fragmentos reales del temario, basa las preguntas "
        f"UNICAMENTE en esto):\n{contexto}\n\n---\n\n"
        f"Tema: {tema}\n"
        f"Numero de preguntas a generar: {cantidad}\n"
        f"Lote numero {numero_lote} (identificador de variedad: {identificador_variedad}).\n"
        f"ENFOQUE OBLIGATORIO de este lote: {enfoque}. Todas las preguntas de "
        "este lote tienen que girar en torno a ese enfoque -- no generes "
        "preguntas genericas que servirian para cualquier lote."
    )

    if enunciados_existentes:
        previas = "\n".join(f"- {e}" for e in enunciados_existentes)
        instrucciones += (
            "\n\nEstas preguntas YA EXISTEN en el banco de este tema (de "
            "este lote, de lotes anteriores de esta misma ejecucion, o de "
            "ejecuciones anteriores del script) -- NO las repitas ni "
            "generes variantes casi identicas (mismo dato o concepto solo "
            f"con las palabras cambiadas o reformulado como sinonimo):\n{previas}"
        )

    # temperature alta (variedad) sigue siendo seguro aqui: response_mime_type
    # fuerza la estructura JSON igualmente, lo que varia es el contenido de
    # las preguntas, no el formato de la respuesta.
    respuesta = cliente.models.generate_content(
        model=MODELO_CHAT,
        contents=instrucciones,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.9,
            response_mime_type="application/json",
            max_output_tokens=16384,
            # Gemini 2.5 Flash reserva parte de max_output_tokens para
            # "pensar" antes de responder (thinking_budget), lo que dejaba
            # muy poco margen para el JSON en si y lo cortaba a mitad
            # (json.loads fallaba con "Unterminated string"/"Expecting ','
            # delimiter"). Se desactiva: esta tarea es extraccion/generacion
            # estructurada a partir de un contexto ya dado, no requiere
            # razonamiento multi-paso.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    datos = json.loads(respuesta.text)
    return datos.get("preguntas", [])


def _pregunta_es_valida(pregunta: dict) -> bool:
    return (
        isinstance(pregunta.get("enunciado"), str)
        and isinstance(pregunta.get("opciones"), list)
        and len(pregunta["opciones"]) == 4
        and isinstance(pregunta.get("respuesta_correcta"), int)
        and 0 <= pregunta["respuesta_correcta"] <= 3
        and isinstance(pregunta.get("justificacion"), str)
    )


def obtener_enunciados_existentes(tema: str) -> list[str]:
    """Enunciados ya guardados en el banco para este tema, de ejecuciones
    anteriores del script (o de lotes previos de esta misma ejecucion). Sin
    esto, cada vez que se vuelve a correr generar_banco.py para el mismo
    tema el modelo no tiene ninguna visibilidad de lo ya generado: empieza
    otra vez por el enfoque "definiciones y conceptos fundamentales" (el
    primero del ciclo rotatorio) y acaba regenerando las mismas preguntas
    basicas una y otra vez, aunque el banco ya tenga decenas de preguntas.
    """
    db = SessionLocal()
    try:
        filas = (
            db.query(PreguntaTest.enunciado)
            .filter(PreguntaTest.tema == tema)
            .all()
        )
        return [enunciado for (enunciado,) in filas]
    finally:
        db.close()


def guardar_preguntas(tema: str, preguntas: list[dict]) -> int:
    db = SessionLocal()
    guardadas = 0
    try:
        for pregunta in preguntas:
            if not _pregunta_es_valida(pregunta):
                print(f"  [omitida] pregunta con formato inesperado: {pregunta}")
                continue

            db.add(
                PreguntaTest(
                    tema=tema,
                    enunciado=pregunta["enunciado"],
                    opciones=pregunta["opciones"],
                    respuesta_correcta=pregunta["respuesta_correcta"],
                    justificacion=pregunta["justificacion"],
                )
            )
            guardadas += 1
        db.commit()
    finally:
        db.close()
    return guardadas


def generar_y_guardar_lotes(
    cliente: genai.Client,
    vectorstore,
    tema: str,
    cantidad: int,
    enunciados_existentes: list[str],
    lote_inicial: int = 1,
) -> tuple[int, int]:
    """Genera y guarda lotes hasta cubrir `cantidad` preguntas NUEVAS
    realmente guardadas (o hasta que Gemini falle/deje de devolver nada).

    Descuenta `restantes` por lo realmente guardado en cada lote, no por el
    tamano pedido: Gemini a veces devuelve menos preguntas de las
    solicitadas sin avisar (mas probable cuanto mas larga es la lista de
    "no repitas esto"), y descontar el tamano pedido dejaba el banco por
    debajo del objetivo real sin que nadie se diera cuenta.
    """
    restantes = cantidad
    lote_actual = lote_inicial
    total_generadas = 0
    total_guardadas = 0

    while restantes > 0:
        tamano = min(TAMANO_LOTE, restantes)
        print(f"\nLote {lote_actual}: pidiendo {tamano} preguntas...")

        try:
            preguntas = generar_preguntas_gemini(
                cliente, vectorstore, tema, tamano, lote_actual, enunciados_existentes
            )
        except APIError as exc:
            print(f"  Error llamando a Gemini en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break
        except json.JSONDecodeError as exc:
            print(f"  Gemini devolvio un JSON invalido en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break

        if not preguntas:
            print(f"  Lote {lote_actual}: Gemini no devolvio ninguna pregunta, se detiene aqui.")
            break

        guardadas = guardar_preguntas(tema, preguntas)
        total_generadas += len(preguntas)
        total_guardadas += guardadas
        print(f"  Lote {lote_actual}: {guardadas}/{len(preguntas)} guardadas.")

        enunciados_existentes.extend(
            p["enunciado"] for p in preguntas if _pregunta_es_valida(p)
        )

        restantes -= guardadas
        lote_actual += 1

    return total_generadas, total_guardadas


def main() -> None:
    print(f"Temas ya usados por el frontend: {', '.join(TEMAS_CONOCIDOS)}")
    print("(puedes usar otro si vas a añadir esa opcion al desplegable, pero")
    print(" tiene que coincidir EXACTAMENTE con lo que mande el frontend)")
    tema = input("Tema: ").strip()
    if not tema:
        print("El tema no puede estar vacio.")
        return

    try:
        cantidad = int(input("Cantidad de preguntas a generar: ").strip())
    except ValueError:
        print("La cantidad tiene que ser un numero entero.")
        return
    if cantidad <= 0:
        print("La cantidad tiene que ser mayor que 0.")
        return

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return
    cliente = genai.Client(api_key=api_key)

    print("Abriendo el indice de conocimiento (puede tardar 1-2 min si aun no existe)...")
    vectorstore = _obtener_vectorstore()

    print(f"\nGenerando {cantidad} preguntas de '{tema}' con {MODELO_CHAT}...")

    # Se siembra con lo que YA hay en el banco para este tema (de
    # ejecuciones anteriores) y se va acumulando con cada lote de esta
    # ejecucion -- antes se reemplazaba en cada vuelta y solo se comparaba
    # contra el lote inmediatamente anterior, asi que un lote 5 no sabia
    # nada de lo generado en el lote 2, y una segunda ejecucion del script
    # no sabia nada de la primera.
    enunciados_existentes = obtener_enunciados_existentes(tema)
    if enunciados_existentes:
        print(f"El banco ya tiene {len(enunciados_existentes)} preguntas de '{tema}'.")

    total_generadas, total_guardadas = generar_y_guardar_lotes(
        cliente, vectorstore, tema, cantidad, enunciados_existentes
    )

    print(
        f"\nListo: {total_guardadas}/{total_generadas} preguntas guardadas en total "
        "en la tabla preguntas_test."
    )


if __name__ == "__main__":
    main()
