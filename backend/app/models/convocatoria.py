from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Convocatoria(Base):
    __tablename__ = "convocatorias"

    id = Column(Integer, primary_key=True, index=True)
    titulo_plaza = Column(String, nullable=False)
    organismo_localidad = Column(String, nullable=False)
    plazo_dias = Column(Integer, nullable=True)
    requisitos_minimos = Column(Text, nullable=True)
    fecha_publicacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # No pedido explicitamente, pero imprescindible: el scraper se ejecuta
    # cada 24h sobre los mismos feeds RSS, y una convocatoria abierta suele
    # seguir apareciendo en el feed varios dias. Sin esta columna (unica),
    # cada ejecucion duplicaria filas y volveria a gastar una llamada a
    # OpenAI por la misma noticia ya procesada.
    url_origen = Column(String, nullable=False, unique=True, index=True)
