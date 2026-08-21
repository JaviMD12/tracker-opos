from sqlalchemy import Column, Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProgresoFlashcard(Base):
    """Progreso de repaso espaciado de un usuario sobre una Flashcard
    concreta (Plan Pro). No existe fila hasta el primer repaso -- una
    flashcard sin fila aqui para un usuario se considera pendiente desde el
    primer momento (ver GET /api/flashcards/due).

    facilidad hace de "estado acumulado" del algoritmo de repeticion
    espaciada (SM-2 simplificado, ver app/services/srs.py): crece cuando el
    usuario marca Facil, baja cuando marca Dificil, y multiplica a
    intervalo_dias en cada repaso en vez de depender de un contador aparte
    de repeticiones consecutivas.
    """

    __tablename__ = "progreso_flashcards"
    __table_args__ = (UniqueConstraint("usuario_id", "flashcard_id"),)

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id"), nullable=False, index=True)
    intervalo_dias = Column(Integer, nullable=False, default=1)
    facilidad = Column(Float, nullable=False, default=2.5)
    fecha_proximo_repaso = Column(Date, nullable=False, server_default=func.current_date())

    usuario = relationship("Usuario", back_populates="progreso_flashcards")
    flashcard = relationship("Flashcard")
