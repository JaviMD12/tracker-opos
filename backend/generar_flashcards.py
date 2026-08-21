"""Script offline para precargar el banco de Flashcards (repeticion espaciada,
Plan Pro). No depende de FastAPI ni de que el servidor este arrancado: se
conecta directamente a la base de datos (SQLite local o Postgres, segun
DATABASE_URL) y llama a Gemini una sola vez por lote.

Reusa el mismo indice RAG que generar_banco.py y el Tutor IA
(app/services/ai_tutor.py, indexado desde app/conocimiento/): se recuperan
fragmentos reales del temario para generar las tarjetas, en vez de dejar que
el modelo invente contenido de su conocimiento general. Tambien reusa la
taxonomia de 6 temas y el mapa tema->documentos de generar_banco.py, para
que el desplegable de Flashcards del frontend coincida con el de Simulacros.

Uso:
    cd backend
    python generar_flashcards.py [cantidad_por_tema]

Sin argumento, genera hasta 30 flashcards por tema. Es idempotente: si un
tema ya tiene esa cantidad o mas, se omite; si tiene menos, solo genera lo
que falta.
"""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from google.genai.errors import APIError  # noqa: E402
from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.flashcard import Flashcard  # noqa: E402
from app.services.ai_tutor import _obtener_vectorstore  # noqa: E402
from generar_banco import (  # noqa: E402
    ENFOQUES_ROTATORIOS,
    MODELO_CHAT,
    TEMAS_CONOCIDOS,
    _recuperar_contexto,
)

CANTIDAD_POR_DEFECTO = 30
TAMANO_LOTE = 20

SYSTEM_PROMPT = (
    "Eres un preparador de oposiciones de bomberos y emergencias. Tu "
    "objetivo es generar tarjetas de memoria (flashcards) de Pregunta/"
    "Respuesta a partir del CONTEXTO que se te proporciona en cada peticion "
    "(fragmentos reales extraidos del temario oficial) -- no uses "
    "conocimiento general propio ni inventes datos, cifras o articulos que "
    "no aparezcan en ese contexto. Extrae los datos mas importantes de ese "
    "texto y genera pares de Pregunta/Respuesta concisos: la pregunta debe "
    "poder responderse de memoria en pocos segundos (una cifra, un plazo, "
    "una definicion corta, el nombre de un articulo/norma), no un tema "
    "abierto para desarrollar. La respuesta debe ser tan breve como sea "
    "posible sin perder precision -- una frase o un dato concreto, nunca un "
    'parrafo. Devuelve UNICAMENTE un objeto JSON valido con esta estructura '
    'exacta: {"flashcards": [{"pregunta": "texto", "respuesta": "texto"}]}.'
    "\n\nVARIEDAD (muy importante, esto se genera en muchos lotes "
    "independientes que no deben solaparse entre si): evita las tarjetas "
    "mas obvias, las 3-4 que cualquiera haria primero -- explora en su "
    "lugar datos concretos, cifras exactas y detalles tecnicos especificos "
    "presentes en el contexto. No repitas preguntas entre si, ni "
    "reformules la misma idea cambiando solo las palabras."
)


def generar_flashcards_gemini(
    cliente: genai.Client,
    vectorstore,
    tema: str,
    cantidad: int,
    numero_lote: int,
    preguntas_existentes: list[str],
) -> list[dict]:
    enfoque = ENFOQUES_ROTATORIOS[(numero_lote - 1) % len(ENFOQUES_ROTATORIOS)]
    contexto = _recuperar_contexto(vectorstore, tema, enfoque)

    instrucciones = (
        f"CONTEXTO (fragmentos reales del temario, basa las tarjetas "
        f"UNICAMENTE en esto):\n{contexto}\n\n---\n\n"
        f"Tema: {tema}\n"
        f"Numero de flashcards a generar: {cantidad}\n"
        f"ENFOQUE OBLIGATORIO de este lote: {enfoque}. Todas las tarjetas de "
        "este lote tienen que girar en torno a ese enfoque."
    )

    if preguntas_existentes:
        previas = "\n".join(f"- {p}" for p in preguntas_existentes)
        instrucciones += (
            "\n\nEstas preguntas YA EXISTEN en el banco de este tema -- NO "
            f"las repitas ni generes variantes casi identicas:\n{previas}"
        )

    respuesta = cliente.models.generate_content(
        model=MODELO_CHAT,
        contents=instrucciones,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.9,
            response_mime_type="application/json",
            max_output_tokens=8192,
            # Igual que en generar_banco.py: es extraccion/generacion
            # estructurada a partir de un contexto ya dado, no requiere
            # razonamiento multi-paso -- sin esto Gemini 2.5 Flash reserva
            # parte del presupuesto de tokens para "pensar" y corta el JSON
            # a mitad.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    datos = json.loads(respuesta.text)
    return datos.get("flashcards", [])


def _flashcard_es_valida(flashcard: dict) -> bool:
    return (
        isinstance(flashcard.get("pregunta"), str)
        and flashcard["pregunta"].strip()
        and isinstance(flashcard.get("respuesta"), str)
        and flashcard["respuesta"].strip()
    )


def obtener_preguntas_existentes(tema: str) -> list[str]:
    db = SessionLocal()
    try:
        filas = db.query(Flashcard.pregunta).filter(Flashcard.tema == tema).all()
        return [pregunta for (pregunta,) in filas]
    finally:
        db.close()


def guardar_flashcards(tema: str, flashcards: list[dict]) -> int:
    db = SessionLocal()
    guardadas = 0
    try:
        for flashcard in flashcards:
            if not _flashcard_es_valida(flashcard):
                print(f"  [omitida] flashcard con formato inesperado: {flashcard}")
                continue

            db.add(
                Flashcard(
                    tema=tema,
                    pregunta=flashcard["pregunta"].strip(),
                    respuesta=flashcard["respuesta"].strip(),
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
    preguntas_existentes: list[str],
    lote_inicial: int = 1,
) -> int:
    restantes = cantidad
    lote_actual = lote_inicial
    total_guardadas = 0

    while restantes > 0:
        tamano = min(TAMANO_LOTE, restantes)
        print(f"\nLote {lote_actual}: pidiendo {tamano} flashcards...")

        try:
            flashcards = generar_flashcards_gemini(
                cliente, vectorstore, tema, tamano, lote_actual, preguntas_existentes
            )
        except APIError as exc:
            print(f"  Error llamando a Gemini en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break
        except json.JSONDecodeError as exc:
            print(f"  Gemini devolvio un JSON invalido en el lote {lote_actual}: {exc}")
            print("  Se detiene aqui, se conservan los lotes ya guardados.")
            break

        if not flashcards:
            print(f"  Lote {lote_actual}: Gemini no devolvio ninguna flashcard, se detiene aqui.")
            break

        guardadas = guardar_flashcards(tema, flashcards)
        total_guardadas += guardadas
        print(f"  Lote {lote_actual}: {guardadas}/{len(flashcards)} guardadas.")

        preguntas_existentes.extend(
            f["pregunta"] for f in flashcards if _flashcard_es_valida(f)
        )

        restantes -= guardadas
        lote_actual += 1

    return total_guardadas


def main() -> None:
    cantidad_objetivo = int(sys.argv[1]) if len(sys.argv) > 1 else CANTIDAD_POR_DEFECTO

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return
    cliente = genai.Client(api_key=api_key)

    print("Abriendo el indice de conocimiento (puede tardar 1-2 min si aun no existe)...")
    vectorstore = _obtener_vectorstore()

    db = SessionLocal()
    conteos = dict(
        db.query(Flashcard.tema, func.count(Flashcard.id)).group_by(Flashcard.tema).all()
    )
    db.close()

    for tema in TEMAS_CONOCIDOS:
        ya_guardadas = conteos.get(tema, 0)
        restantes = cantidad_objetivo - ya_guardadas
        if restantes <= 0:
            print(f"\n=== TEMA: {tema} -- ya tiene {ya_guardadas}, se omite ===")
            continue

        print(f"\n=== TEMA: {tema} (tiene {ya_guardadas}, faltan {restantes}) ===")
        preguntas_existentes = obtener_preguntas_existentes(tema)
        lote_inicial = (ya_guardadas // TAMANO_LOTE) + 1

        generar_y_guardar_lotes(
            cliente, vectorstore, tema, restantes, preguntas_existentes, lote_inicial
        )

    print("\nListo: todos los temas cubiertos hasta el objetivo.")


if __name__ == "__main__":
    main()
