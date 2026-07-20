"""Vacia por completo el banco de preguntas de los Simulacros IA (tabla
preguntas_test / modelo PreguntaTest), antes de recargarlo con el
generar_banco.py mejorado (lotes + enfoques rotatorios).

Uso:
    cd backend
    python purgar_preguntas.py
"""

from app.database import SessionLocal
from app.models.pregunta_test import PreguntaTest

db = SessionLocal()
try:
    borradas = db.query(PreguntaTest).delete()
    db.commit()
    print(f"Banco de preguntas vaciado: {borradas} filas eliminadas de 'preguntas_test'.")
finally:
    db.close()
