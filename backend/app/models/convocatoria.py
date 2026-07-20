from datetime import datetime, timezone

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

    # Fecha limite real (fecha_publicacion + plazo_dias, calculada una vez al
    # scrapear, ver services/scraper_boletines.py). plazo_dias por si solo es
    # un numero fijo extraido del texto una unica vez -- sin esta fecha
    # absoluta, "dias restantes" se quedaba congelado para siempre en vez de
    # ir bajando dia a dia. Nullable porque convocatorias antiguas (de antes
    # de esta columna) o sin plazo_dias detectado no tienen forma de calcularla.
    fecha_limite = Column(DateTime(timezone=True), nullable=True)

    # No pedido explicitamente, pero imprescindible: el scraper se ejecuta
    # cada 24h sobre los mismos feeds RSS, y una convocatoria abierta suele
    # seguir apareciendo en el feed varios dias. Sin esta columna (unica),
    # cada ejecucion duplicaria filas y volveria a gastar una llamada a
    # OpenAI por la misma noticia ya procesada.
    url_origen = Column(String, nullable=False, unique=True, index=True)

    @property
    def dias_restantes(self) -> int | None:
        """Dias reales que quedan hasta fecha_limite, calculado en el momento
        de la peticion (no un numero fijo guardado): baja solo con el paso
        del tiempo real, y puede salir negativo si el plazo ya paso.

        fecha_limite se guarda siempre a partir de datetime.now(timezone.utc),
        pero SQLite no conserva el tzinfo al releerlo (a diferencia de
        Postgres, que si lo hace con DateTime(timezone=True)): si vuelve
        "naive", se asume UTC en vez de dejar que reste explote comparando
        aware con naive.
        """
        if self.fecha_limite is None:
            return None
        fecha_limite = self.fecha_limite
        if fecha_limite.tzinfo is None:
            fecha_limite = fecha_limite.replace(tzinfo=timezone.utc)
        return (fecha_limite - datetime.now(timezone.utc)).days
