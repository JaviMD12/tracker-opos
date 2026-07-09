import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Produccion (Render u otro proveedor de Postgres). Algunos proveedores
    # siguen dando la URL con el esquema antiguo "postgres://", que
    # SQLAlchemy 1.4+/2.x ya no acepta: hay que reescribirlo a "postgresql://".
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    # pool_pre_ping evita errores por conexiones que Postgres cierra tras un
    # rato inactivas (habitual en el Postgres gratuito de Render).
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    # Desarrollo local: SQLite con ruta absoluta a la raiz del proyecto
    # (tracker-oposiciones/oposiciones.db), sin importar desde que directorio
    # de trabajo se arranque el servidor.
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/app
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(_APP_DIR))  # tracker-oposiciones
    DB_PATH = os.path.join(_PROJECT_ROOT, "oposiciones.db")

    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    # check_same_thread es exclusivo del driver de SQLite; no se pasa en la
    # rama de Postgres porque psycopg2 no lo entiende.
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
