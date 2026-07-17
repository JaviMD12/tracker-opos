from pathlib import Path

from dotenv import load_dotenv

# Cargar backend/.env con ruta absoluta ANTES de importar los routers: pagos.py
# lee STRIPE_SECRET_KEY al importarse, asi que el orden aqui es critico.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models.convocatoria import Convocatoria  # noqa: F401,E402 (registra el modelo en Base)
from app.models.marca import MarcaFisica  # noqa: F401,E402 (registra el modelo en Base)
from app.models.resultado_simulacro import ResultadoSimulacro  # noqa: F401,E402 (registra el modelo en Base)
from app.models.sesion_estudio import SesionEstudio  # noqa: F401,E402 (registra el modelo en Base)
from app.models.simulacro import SimulacroTeorico  # noqa: F401,E402 (registra el modelo en Base)
from app.models.usuario import Usuario  # noqa: F401,E402 (registra el modelo en Base)
from app.models.workout import Workout  # noqa: F401,E402 (registra el modelo en Base)
from app.routers import (  # noqa: E402
    actividad,
    auth,
    chat,
    convocatorias,
    dashboard,
    marcas,
    pagos,
    pro,
    simulacros,
    teorica,
    tutor,
    usuarios,
    workouts,
)
from app.services.scraper_boletines import ejecutar_scraping_boletines  # noqa: E402
from app.services.security import SECRET_KEY  # noqa: E402

Base.metadata.create_all(bind=engine)


def _asegurar_columna(tabla: str, columna: str, tipo_sql: str) -> None:
    """create_all no anade columnas a tablas que ya existen. Sin Alembic,
    esto asegura que columnas nuevas (ej. stripe_customer_id) esten presentes
    en bases de datos creadas antes de este cambio, sin borrar/recrear la BD."""
    columnas_existentes = {c["name"] for c in inspect(engine).get_columns(tabla)}
    if columna not in columnas_existentes:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo_sql}"))


_asegurar_columna("usuarios", "stripe_customer_id", "VARCHAR")
_asegurar_columna("usuarios", "tour_premium_completado", "BOOLEAN NOT NULL DEFAULT false")

app = FastAPI(title="Tracker Analitico de Oposiciones")

# Requerido por Authlib para guardar el state/nonce del login con Google entre
# la redireccion a accounts.google.com y la vuelta a /api/auth/google/callback.
# https_only=True: en produccion siempre se sirve por HTTPS (detras del
# proxy), asi que la cookie de sesion se marca "Secure" explicitamente en vez
# de depender del valor por defecto (False). same_site="lax" (ya es el valor
# por defecto, se deja explicito a proposito): permite que la cookie viaje en
# la redireccion GET de vuelta desde accounts.google.com -- es exactamente el
# caso que SameSite=Lax esta diseñado para permitir, "strict" la bloquearia.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=True,
)

app.include_router(actividad.router)
app.include_router(auth.router)
app.include_router(marcas.router)
app.include_router(teorica.router)
app.include_router(dashboard.router)
app.include_router(pro.router)
app.include_router(pagos.router)
app.include_router(chat.router)
app.include_router(workouts.router)
app.include_router(convocatorias.router)
app.include_router(tutor.router)
app.include_router(simulacros.router)
app.include_router(usuarios.router)

# Cron del scraper de boletines (BOE/BOJA): se ejecuta a las 03:00 (hora de
# Madrid) para no competir por recursos con el trafico normal de la app.
# Nota: con varios workers (gunicorn -w N en produccion), cada worker crearia
# su propio scheduler y el job se dispararia N veces a esa hora; el
# UniqueConstraint de Convocatoria.url_origen evita duplicados en BD, pero
# convendria revisar esto (p.ej. un solo worker dedicado al cron) antes de
# escalar a mas de un worker en Render.
scheduler = BackgroundScheduler(timezone="Europe/Madrid")


@app.on_event("startup")
def iniciar_scheduler_boletines():
    scheduler.add_job(
        ejecutar_scraping_boletines,
        trigger=CronTrigger(hour=3, minute=0),
        id="scraping_boletines_diario",
        replace_existing=True,
    )
    scheduler.start()


@app.on_event("shutdown")
def detener_scheduler_boletines():
    scheduler.shutdown(wait=False)


@app.middleware("http")
async def sin_cache_en_frontend(request, call_next):
    """StaticFiles no manda Cache-Control por defecto: sin esto, el navegador
    puede quedarse con una copia vieja de index.html/css/js durante dias (cache
    heuristica) y cambios reales en el codigo no se ven ni con F5 normal, solo
    con hard-refresh. no-cache obliga a revalidar (If-None-Match) en cada
    carga; si el archivo no cambio, el servidor responde 304 igualmente
    rapido, asi que no cuesta rendimiento real."""
    response = await call_next(request)
    if request.method == "GET" and not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
