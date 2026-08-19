from sqlalchemy import Column, Integer, Float, Date, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class MarcaFisica(Base):
    __tablename__ = "marcas_fisicas"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    # 'hombre' / 'mujer' -- el baremo oficial (ver baremos_fisicas.json) fija
    # marcas distintas por sexo para las 4 pruebas. Default 'hombre' solo
    # para no romper filas ya existentes al añadir la columna (ver
    # _asegurar_columna en app/main.py); toda fila nueva la fija de forma
    # explicita via MarcaFisicaCreate, sin depender de este default.
    sexo = Column(String(10), nullable=False, server_default="hombre")

    dominadas = Column(Integer, nullable=False)          # repeticiones
    sprint_100m = Column(Float, nullable=False)          # segundos (con decimales)
    carrera_1500m = Column(Integer, nullable=False)      # segundos totales
    natacion_100m = Column(Integer, nullable=False)      # segundos totales

    usuario = relationship("Usuario", back_populates="marcas_fisicas")
