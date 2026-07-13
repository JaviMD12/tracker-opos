from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_pro = Column(Boolean, nullable=False, default=False)
    fecha_registro = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    marcas_fisicas = relationship(
        "MarcaFisica", back_populates="usuario", cascade="all, delete-orphan"
    )
    simulacros_teoricos = relationship(
        "SimulacroTeorico", back_populates="usuario", cascade="all, delete-orphan"
    )
    workouts = relationship(
        "Workout", back_populates="usuario", cascade="all, delete-orphan"
    )
