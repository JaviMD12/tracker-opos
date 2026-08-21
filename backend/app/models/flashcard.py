from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class Flashcard(Base):
    """Banco de flashcards Pregunta/Respuesta (Plan Pro), generado offline
    con generar_flashcards.py a partir del mismo indice RAG que usa el Tutor
    IA (ver app/services/ai_tutor.py). El progreso de repaso por usuario vive
    aparte, en ProgresoFlashcard (ver models/progreso_flashcard.py) -- esta
    tabla es solo el contenido, compartido entre todos los usuarios Pro."""

    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    tema = Column(String, nullable=False, index=True)
    pregunta = Column(Text, nullable=False)
    respuesta = Column(Text, nullable=False)
