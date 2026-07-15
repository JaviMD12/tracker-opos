from sqlalchemy import Column, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SesionEstudio(Base):
    """Sesion de estudio/enfoque (Pomodoro) completada por el usuario.

    Se guarda una fila por cada ciclo de trabajo completado en el Modo
    Enfoque (no en los descansos), para alimentar la mitad "teorica" del
    heatmap de actividad del dashboard.
    """

    __tablename__ = "sesiones_estudio"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    duracion_minutos = Column(Integer, nullable=False)

    usuario = relationship("Usuario", back_populates="sesiones_estudio")
