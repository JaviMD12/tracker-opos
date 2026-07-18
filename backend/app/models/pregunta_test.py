from sqlalchemy import Column, Integer, JSON, String, Text

from app.database import Base


class PreguntaTest(Base):
    """Banco de preguntas precargado para los Simulacros IA (Plan Pro).

    Sustituye a la generacion en vivo via RAG+OpenAI en cada peticion
    (services.ai_tutor.generar_simulacro_test, eliminada): el banco se rellena
    offline con generar_banco.py, y el endpoint /api/simulacros/generar solo
    hace un SELECT aleatorio sobre esta tabla, bajando el tiempo de respuesta
    de varios segundos a milisegundos.
    """

    __tablename__ = "preguntas_test"

    id = Column(Integer, primary_key=True, index=True)
    tema = Column(String, nullable=False, index=True)
    enunciado = Column(Text, nullable=False)
    opciones = Column(JSON, nullable=False)
    respuesta_correcta = Column(Integer, nullable=False)
    justificacion = Column(Text, nullable=False)
