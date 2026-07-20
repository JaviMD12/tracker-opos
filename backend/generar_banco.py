"""Script offline para precargar el Banco de Preguntas de los Simulacros IA.

No depende de FastAPI ni de que el servidor este arrancado: se conecta
directamente a la base de datos (SQLite local o Postgres, segun DATABASE_URL)
y llama a OpenAI una sola vez por lote, en vez de en cada peticion del
frontend. Uso:

    cd backend
    python generar_banco.py

Pide por consola el tema y la cantidad de preguntas a generar.
"""

import json
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from openai import OpenAIError  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.pregunta_test import PreguntaTest  # noqa: E402

MODELO_CHAT = "gpt-4o-mini"

# Pedir de golpe muchas preguntas choca con el limite de tokens de salida de
# OpenAI (el modelo simplemente devuelve menos de las pedidas, sin avisar).
# Por eso las cantidades grandes se trocean en varias llamadas mas pequeñas.
TAMANO_LOTE = 20

TEMAS_CONOCIDOS = ["Legislacion", "Hidraulica", "Fuego"]

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
    "objetivo es generar preguntas de examen tipo test a partir del temario "
    "oficial. Usa vocabulario tecnico preciso (por ejemplo, usa 'hidrante' en "
    "lugar de terminos genericos como 'aparato'). Cada pregunta debe tener "
    "exactamente 4 opciones, con una unica respuesta correcta y una "
    "justificacion breve de por que lo es. Devuelve UNICAMENTE un objeto JSON "
    'valido con esta estructura exacta: {"preguntas": [{"enunciado": "texto", '
    '"opciones": ["A", "B", "C", "D"], "respuesta_correcta": 0, '
    '"justificacion": "por que es correcta"}]}. El campo "respuesta_correcta" '
    "es el indice (0 a 3) de la opcion valida dentro de \"opciones\".\n\n"
    "VARIEDAD (muy importante, esto se genera en muchos lotes independientes "
    "que no deben solaparse entre si): evita las preguntas mas obvias sobre "
    "el tema, las 3-4 que cualquiera haria primero -- explora en su lugar "
    "aspectos concretos, casos particulares y detalles tecnicos especificos. "
    "No repitas preguntas entre si dentro del mismo lote, ni reformules la "
    "misma idea cambiando solo las palabras."
)


def generar_preguntas_openai(
    tema: str,
    cantidad: int,
    numero_lote: int,
    enunciados_lote_anterior: list[str],
) -> list[dict]:
    # temperature alta (variedad) sigue siendo seguro aqui: response_format
    # json_object fuerza la estructura igualmente, lo que varia es el
    # contenido de las preguntas, no el formato de la respuesta.
    llm = ChatOpenAI(
        model=MODELO_CHAT,
        temperature=0.9,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    enfoque = ENFOQUES_ROTATORIOS[(numero_lote - 1) % len(ENFOQUES_ROTATORIOS)]
    identificador_variedad = random.randint(100_000, 999_999)

    instrucciones = (
        f"Tema: {tema}\n"
        f"Numero de preguntas a generar: {cantidad}\n"
        f"Lote numero {numero_lote} (identificador de variedad: {identificador_variedad}).\n"
        f"ENFOQUE OBLIGATORIO de este lote: {enfoque}. Todas las preguntas de "
        "este lote tienen que girar en torno a ese enfoque -- no generes "
        "preguntas genericas que servirian para cualquier lote."
    )

    if enunciados_lote_anterior:
        previas = "\n".join(f"- {e}" for e in enunciados_lote_anterior)
        instrucciones += (
            "\n\nEstas preguntas ya se generaron en el lote anterior de este "
            "mismo tema -- NO las repitas ni generes variantes casi "
            "identicas (mismo dato o concepto solo con las palabras "
            f"cambiadas):\n{previas}"
        )

    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=instrucciones),
    ]
    respuesta = llm.invoke(mensajes)
    datos = json.loads(respuesta.content)
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

    num_lotes = (cantidad + TAMANO_LOTE - 1) // TAMANO_LOTE
    print(
        f"\nGenerando {cantidad} preguntas de '{tema}' con {MODELO_CHAT}, "
        f"en {num_lotes} lote(s) de hasta {TAMANO_LOTE}..."
    )

    total_generadas = 0
    total_guardadas = 0
    restantes = cantidad
    lote_actual = 1
    enunciados_lote_anterior: list[str] = []

    while restantes > 0:
        tamano = min(TAMANO_LOTE, restantes)
        print(f"\nLote {lote_actual}/{num_lotes}: pidiendo {tamano} preguntas...")

        try:
            preguntas = generar_preguntas_openai(
                tema, tamano, lote_actual, enunciados_lote_anterior
            )
        except OpenAIError as exc:
            print(f"  Error llamando a OpenAI en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break
        except json.JSONDecodeError as exc:
            print(f"  OpenAI devolvio un JSON invalido en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break

        if not preguntas:
            print(f"  Lote {lote_actual}: OpenAI no devolvio ninguna pregunta, se detiene aqui.")
            break

        guardadas = guardar_preguntas(tema, preguntas)
        total_generadas += len(preguntas)
        total_guardadas += guardadas
        print(f"  Lote {lote_actual}: {guardadas}/{len(preguntas)} guardadas.")

        # Se pasa al siguiente lote para que sepa que NO debe repetir.
        enunciados_lote_anterior = [
            p["enunciado"] for p in preguntas if _pregunta_es_valida(p)
        ]

        restantes -= tamano
        lote_actual += 1

    print(
        f"\nListo: {total_guardadas}/{total_generadas} preguntas guardadas en total "
        "en la tabla preguntas_test."
    )


if __name__ == "__main__":
    main()
