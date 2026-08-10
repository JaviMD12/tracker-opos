from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class Waitlist(Base):
    """Email de alguien interesado en la Zona Premium mientras el checkout
    de Stripe esta pausado (ver ENABLE_STRIPE en routers/pagos.py). No esta
    ligado a Usuario a proposito: no exige estar registrado en la app para
    apuntarse."""

    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True, index=True)
    fecha_registro = Column(DateTime(timezone=True), server_default=func.now())
