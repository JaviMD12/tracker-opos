from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SimulacroTeorico(Base):
    __tablename__ = "simulacros_teoricos"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    aciertos = Column(Integer, nullable=False)
    fallos = Column(Integer, nullable=False)
    blancos = Column(Integer, nullable=False)
    nota_calculada = Column(Float, nullable=False)

    usuario = relationship("Usuario", back_populates="simulacros_teoricos")
