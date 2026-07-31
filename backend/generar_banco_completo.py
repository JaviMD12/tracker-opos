"""Genera (o completa hasta un objetivo) el banco de preguntas para TODOS
los temas conocidos de una sola vez, sin preguntar nada por consola.

Pensado para desplegar el banco en un servidor (VPS, Render...) tras un
`git pull`, donde `backend/oposiciones.db` (o la Postgres de produccion) no
tiene todavia las preguntas que si existen en la maquina de desarrollo --
`*.db` esta en `.gitignore` a proposito, asi que el banco nunca viaja con el
codigo y hay que regenerarlo en cada entorno donde haga falta.

Uso:
    cd backend
    python generar_banco_completo.py [cantidad_por_tema]

Si no se indica cantidad, usa 100 por tema. Es idempotente: si un tema ya
tiene esa cantidad o mas, se omite; si tiene menos, solo genera lo que
falta (usa generar_y_guardar_lotes(), que descuenta por preguntas
realmente guardadas, no por las pedidas).
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import func

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from google import genai  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.pregunta_test import PreguntaTest  # noqa: E402
from app.services.ai_tutor import _obtener_vectorstore  # noqa: E402
from generar_banco import (  # noqa: E402
    TAMANO_LOTE,
    TEMAS_CONOCIDOS,
    generar_y_guardar_lotes,
    obtener_enunciados_existentes,
)

CANTIDAD_POR_DEFECTO = 100


def main() -> None:
    cantidad_objetivo = (
        int(sys.argv[1]) if len(sys.argv) > 1 else CANTIDAD_POR_DEFECTO
    )

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return
    cliente = genai.Client(api_key=api_key)

    print("Abriendo el indice de conocimiento (puede tardar 1-2 min si aun no existe)...")
    vectorstore = _obtener_vectorstore()

    db = SessionLocal()
    conteos = dict(
        db.query(PreguntaTest.tema, func.count(PreguntaTest.id))
        .group_by(PreguntaTest.tema)
        .all()
    )
    db.close()

    for tema in TEMAS_CONOCIDOS:
        ya_guardadas = conteos.get(tema, 0)
        restantes = cantidad_objetivo - ya_guardadas
        if restantes <= 0:
            print(f"\n=== TEMA: {tema} -- ya tiene {ya_guardadas}, se omite ===")
            continue

        print(f"\n=== TEMA: {tema} (tiene {ya_guardadas}, faltan {restantes}) ===")
        enunciados_existentes = obtener_enunciados_existentes(tema)
        lote_inicial = (ya_guardadas // TAMANO_LOTE) + 1

        generar_y_guardar_lotes(
            cliente, vectorstore, tema, restantes, enunciados_existentes, lote_inicial
        )

    print("\nListo: todos los temas cubiertos hasta el objetivo.")


if __name__ == "__main__":
    main()
