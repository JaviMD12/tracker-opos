import os
import secrets

import httpx
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas import Token, UsuarioCreate, UsuarioOut
from app.services.security import (
    create_access_token,
    generar_token_reset,
    get_password_hash,
    oauth,
    verificar_token_reset,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

DOMINIO_APP = os.environ.get("DOMINIO_APP", "https://opotracker.tech")
WEBHOOK_RECUPERACION_URL = os.environ.get("WEBHOOK_RECUPERACION_URL")


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UsuarioCreate, db: Session = Depends(get_db)):
    ya_existe = db.query(Usuario).filter(Usuario.email == payload.email).first()
    if ya_existe is not None:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    usuario = Usuario(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if usuario is None or not verify_password(form_data.password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(usuario.id)})
    return Token(access_token=access_token)


# ---------- Login con Google (OAuth2 / OpenID Connect) ----------


@router.get("/google/login")
async def google_login(request: Request):
    """Redirige al usuario a la pantalla de consentimiento de Google."""
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """Recibe la vuelta de Google, crea el usuario si hace falta y redirige
    al frontend con nuestro propio JWT en la query string."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(
            status_code=400, detail=f"No se pudo completar el login con Google: {exc}"
        ) from exc

    userinfo = token.get("userinfo")
    email = userinfo.get("email") if userinfo else None
    if not email:
        raise HTTPException(status_code=400, detail="Google no devolvio un email valido")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        # Cuenta creada via Google: contraseña aleatoria e inaccesible (nadie
        # la conoce, no se envia a ningun sitio); este usuario solo podra
        # entrar por Google hasta que use "olvido mi contraseña".
        usuario = Usuario(
            email=email,
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    access_token = create_access_token(data={"sub": str(usuario.id)})
    return RedirectResponse(url=f"{DOMINIO_APP}/?token={access_token}")


# ---------- Recuperacion de contraseña (webhook) ----------


class OlvidoPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetPasswordIn(BaseModel):
    token: str
    nueva_password: str = Field(min_length=8, max_length=128)


MENSAJE_GENERICO_OLVIDO = (
    "Si el email existe en nuestro sistema, recibiras un enlace de recuperacion en breve."
)


@router.post("/olvido-password")
async def olvido_password(payload: OlvidoPasswordIn, db: Session = Depends(get_db)):
    """Siempre responde con el mismo mensaje generico, exista o no el email,
    para no revelar que cuentas estan registradas (enumeration attack)."""
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()

    if usuario is not None and WEBHOOK_RECUPERACION_URL:
        token_reset = generar_token_reset(usuario.email)
        link = f"{DOMINIO_APP}/?reset_token={token_reset}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    WEBHOOK_RECUPERACION_URL,
                    json={"email": usuario.email, "link": link},
                )
        except httpx.HTTPError as exc:
            # No se revela el fallo al usuario (mismo mensaje generico), pero
            # queda constancia en el log del servidor para depurar el webhook.
            print(f"[olvido-password] fallo el webhook de recuperacion: {exc}")

    return {"mensaje": MENSAJE_GENERICO_OLVIDO}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    email = verificar_token_reset(payload.token)
    if email is None:
        raise HTTPException(
            status_code=400, detail="El enlace de recuperacion no es valido o ha caducado"
        )

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        raise HTTPException(
            status_code=400, detail="El enlace de recuperacion no es valido o ha caducado"
        )

    usuario.hashed_password = get_password_hash(payload.nueva_password)
    db.commit()

    return {"mensaje": "Contraseña actualizada correctamente"}
