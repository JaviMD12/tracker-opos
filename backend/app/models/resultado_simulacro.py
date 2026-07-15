from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ResultadoSimulacro(Base):
    """Resultado de un simulacro tipo test generado por IA (Plan Pro).

    Distinto de `SimulacroTeorico` (el autoinforme manual de aciertos/fallos/
    blancos del dashboard gratuito): este modelo registra las notas de los
    examenes generados por `services.ai_tutor.generar_simulacro_test`, para
    alimentar en el futuro el dashboard con la evolucion por tema.
    """

    __tablename__ = "resultados_simulacro"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    tema = Column(String, nullable=False)
    aciertos = Column(Integer, nullable=False)
    total_preguntas = Column(Integer, nullable=False)

    usuario = relationship("Usuario", back_populates="resultados_simulacro")
