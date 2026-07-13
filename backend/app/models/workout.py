from sqlalchemy import Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, server_default=func.current_date())
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    workout_type = Column(String, nullable=False)  # "Fuerza" | "Carrera" | "Natacion"
    notes = Column(String, nullable=True)

    # Fuerza
    exercise_name = Column(String, nullable=True)
    weight_kg = Column(Float, nullable=True)
    reps = Column(Integer, nullable=True)

    # Carrera / Natacion
    distance_km = Column(Float, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    usuario = relationship("Usuario", back_populates="workouts")
