from pathlib import Path

from dotenv import load_dotenv

# Cargar backend/.env con ruta absoluta ANTES de importar los routers: pagos.py
# lee STRIPE_SECRET_KEY al importarse, asi que el orden aqui es critico.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.models.marca import MarcaFisica  # noqa: F401,E402 (registra el modelo en Base)
from app.models.simulacro import SimulacroTeorico  # noqa: F401,E402 (registra el modelo en Base)
from app.models.usuario import Usuario  # noqa: F401,E402 (registra el modelo en Base)
from app.routers import auth, chat, dashboard, marcas, pagos, pro, teorica  # noqa: E402
from app.services.security import SECRET_KEY  # noqa: E402

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tracker Analitico de Oposiciones")

# Requerido por Authlib para guardar el state/nonce del login con Google entre
# la redireccion a accounts.google.com y la vuelta a /api/auth/google/callback.
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(auth.router)
app.include_router(marcas.router)
app.include_router(teorica.router)
app.include_router(dashboard.router)
app.include_router(pro.router)
app.include_router(pagos.router)
app.include_router(chat.router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
