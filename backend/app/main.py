import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Cargar backend/.env con ruta absoluta ANTES de importar los routers: pagos.py
# lee STRIPE_SECRET_KEY al importarse, asi que el orden aqui es critico.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.rate_limit import limiter  # noqa: E402
from app.models.convocatoria import Convocatoria  # noqa: F401,E402 (registra el modelo en Base)
from app.models.marca import MarcaFisica  # noqa: F401,E402 (registra el modelo en Base)
from app.models.pregunta_test import PreguntaTest  # noqa: F401,E402 (registra el modelo en Base)
from app.models.resultado_simulacro import ResultadoSimulacro  # noqa: F401,E402 (registra el modelo en Base)
from app.models.sesion_estudio import SesionEstudio  # noqa: F401,E402 (registra el modelo en Base)
from app.models.simulacro import SimulacroTeorico  # noqa: F401,E402 (registra el modelo en Base)
from app.models.usuario import Usuario  # noqa: F401,E402 (registra el modelo en Base)
from app.models.waitlist import Waitlist  # noqa: F401,E402 (registra el modelo en Base)
from app.models.workout import Workout  # noqa: F401,E402 (registra el modelo en Base)
from app.routers import (  # noqa: E402
    actividad,
    auth,
    chat,
    contacto,
    convocatorias,
    dashboard,
    marcas,
    pagos,
    pro,
    simulacros,
    teorica,
    tutor,
    usuarios,
    waitlist,
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
_asegurar_columna("convocatorias", "fecha_limite", "TIMESTAMP")


def _backfill_fecha_limite_convocatorias() -> None:
    """Calcula fecha_limite (fecha_publicacion + plazo_dias) para
    convocatorias scrapeadas antes de que existiera esta columna. Idempotente:
    en cada arranque solo toca las filas que todavia no la tengan, asi que en
    arranques posteriores no hace nada (0 filas pendientes)."""
    db = SessionLocal()
    try:
        pendientes = (
            db.query(Convocatoria)
            .filter(Convocatoria.fecha_limite.is_(None), Convocatoria.plazo_dias.isnot(None))
            .all()
        )
        for convocatoria in pendientes:
            convocatoria.fecha_limite = convocatoria.fecha_publicacion + timedelta(
                days=convocatoria.plazo_dias
            )
        if pendientes:
            db.commit()
    finally:
        db.close()


_backfill_fecha_limite_convocatorias()

app = FastAPI(title="Tracker Analitico de Oposiciones")

# CORS: reusa DOMINIO_APP (mismo patron que auth.py/pagos.py) en vez de una
# variable nueva. El frontend se sirve desde este mismo FastAPI (StaticFiles
# mas abajo), asi que las llamadas normales ya son same-origin; esto es
# defensa explicita para que ninguna otra web pueda leer las respuestas de la
# API desde el navegador de un usuario. Nunca "*" junto con
# allow_credentials=True -- los navegadores lo rechazan directamente por
# spec, y aqui hace falta True porque el login con Google usa la cookie de
# SessionMiddleware de abajo.
DOMINIO_APP = os.environ.get("DOMINIO_APP", "https://opotracker.tech")
# .rstrip("/"): DOMINIO_APP se usa en otros sitios (auth.py, pagos.py) con
# una barra final incluida via f"{DOMINIO_APP}/?..." -- pero un origen CORS
# nunca lleva barra final ("https://x.com/" no matchea nunca el Origin real
# que manda el navegador, que siempre es "https://x.com"). Bug real
# encontrado en pruebas locales: con la barra puesta, ninguna peticion
# cross-origin recibia jamas el header Access-Control-Allow-Origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[DOMINIO_APP.rstrip("/")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Limite de tamano de peticion (defensa en profundidad): nginx ya corta esto
# antes de que llegue a Python de verdad (client_max_body_size en el VPS),
# pero esta capa cubre el caso de correr detras de otro proxy sin ese limite,
# o si nginx se reconfigura mal algun dia. Solo mira Content-Length -- no
# protege contra un body chunked que mienta esa cabecera, para eso nginx es
# quien de verdad corta la conexion a nivel de red.
MAX_BODY_BYTES = 2 * 1024 * 1024  # 2MB, generoso para chat/formularios


class LimiteTamanoBody(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Petición demasiado grande."})
        return await call_next(request)


app.add_middleware(LimiteTamanoBody)

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

# Rate limiting (slowapi): app.state.limiter es donde el decorador
# @limiter.limit(...) de cada ruta busca la instancia compartida. El handler
# personalizado sustituye el 429 generico de slowapi por el mensaje en
# español que espera el frontend (ver mostrarToast() en el chat del Tutor IA).
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def manejador_limite_excedido(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Has alcanzado el límite de consultas por hora. Tómate un descanso y vuelve en un rato."
        },
    )


app.include_router(actividad.router)
app.include_router(auth.router)
app.include_router(contacto.router)
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
app.include_router(waitlist.router)

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


# Content-Security-Policy: calculada a mano revisando exactamente que carga
# el frontend hoy (index.html, main.js, style.css), no copiada de una
# plantilla generica -- una CSP demasiado estricta rompe la web en silencio
# (la petencion bloqueada no lanza una excepcion en JS, solo un aviso en la
# consola del navegador que nadie ve en produccion). Inventario real:
# - script-src: cdn.tailwindcss.com, cdn.jsdelivr.net (Chart.js/marked/
#   DOMPurify), plausible.io. Sin bloques <script> inline en index.html,
#   asi que NO hace falta 'unsafe-inline' aqui.
# - style-src: Tailwind CDN inyecta un <style> con las clases compiladas en
#   tiempo real en el propio navegador -- eso es intrinsecamente "inline" y
#   distinto en cada carga, asi que no se puede fijar con un hash. 'unsafe-
#   inline' aqui es el precio real de usar el CDN de Tailwind en vez de un
#   build compilado; migrar a un build quitaria esta necesidad, pero es un
#   cambio de arquitectura aparte, no algo para colar dentro de esto.
# - img-src: fotos de Unsplash (hero del login, texturas de las tarjetas),
#   mas data: (iconos nativos de <input type=date>/<select> que Tailwind
#   pinta como data-URI).
# - connect-src: 'self' para las llamadas a /api/*, mas plausible.io porque
#   su propio script manda sus eventos de analitica ahi -- una peticion que
#   dispara SU codigo pero que sigue corriendo dentro de nuestra pagina, y
#   por tanto sujeta a nuestra CSP igualmente.
# - media-src: cdn.pixabay.com -- el sonido de la alarma del Pomodoro
#   (new Audio(...) en main.js), facil de pasar por alto si solo se mira
#   index.html.
# - object-src 'none', base-uri 'self', frame-ancestors 'none': sin plugins,
#   sin <base> dinamico, sin necesidad de que nadie empotre esto en un
#   <iframe> (complementa a X-Frame-Options: DENY de arriba).
CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://plausible.io; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://images.unsplash.com; "
    "font-src 'self'; "
    "connect-src 'self' https://plausible.io; "
    "media-src https://cdn.pixabay.com; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = CSP
    # HSTS solo tiene sentido porque SIEMPRE se sirve por HTTPS (detras de
    # nginx en el VPS) -- si esto se ejecutara alguna vez solo en HTTP puro
    # (dev local sin proxy), la cabecera no hace nada malo, el navegador
    # simplemente la ignora fuera de HTTPS.
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


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
