from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MarcaFisica(Base):
    __tablename__ = "marcas_fisicas"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    dominadas = Column(Integer, nullable=False)          # repeticiones
    sprint_100m = Column(Float, nullable=False)          # segundos (con decimales)
    carrera_1500m = Column(Integer, nullable=False)      # segundos totales
    natacion_100m = Column(Integer, nullable=False)      # segundos totales

    usuario = relationship("Usuario", back_populates="marcas_fisicas")
