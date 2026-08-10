import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas import Token, UsuarioCreate, UsuarioOut
from app.services.rate_limit import limiter
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


@router.post("/registro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def registrar_usuario(request: Request, payload: UsuarioCreate, db: Session = Depends(get_db)):
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
@limiter.limit("10/minute")
def login(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
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
        raise HTTPException(status_code=400, detail="Google no devolvió un email válido")

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


# ---------- Recuperacion de contraseña (email real via Gmail SMTP) ----------


class OlvidoPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ResetPasswordIn(BaseModel):
    token: str
    nueva_password: str = Field(min_length=8, max_length=128)


MENSAJE_GENERICO_OLVIDO = (
    "Si el email existe en nuestro sistema, recibirás un enlace de recuperación en breve."
)


def _enviar_email_recuperacion(destinatario: str, link: str) -> None:
    """Se ejecuta en un BackgroundTask, ya con la respuesta HTTP enviada al
    usuario -- mismo patron que routers/contacto.py::_enviar_email_sugerencia,
    reusando las mismas variables SMTP_* del .env (antes esto usaba un
    webhook generico que apuntaba a webhook.site y no mandaba nada real).
    Si falla, no hay forma de avisar al usuario sin romper la proteccion
    anti-enumeracion (el mensaje de la ruta ya se envio y es siempre
    generico); el fallo solo queda en el log del servidor."""
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        print("[olvido-password] SMTP no configurado en .env, no se envia el email de recuperacion.")
        return

    correo = MIMEMultipart("alternative")
    correo["From"] = smtp_user
    correo["To"] = destinatario
    correo["Subject"] = "Recupera tu contraseña - Tracker Oposiciones"

    texto_plano = (
        "Has solicitado recuperar tu contraseña en Tracker Oposiciones.\n\n"
        f"Abre este enlace para elegir una nueva (caduca en 15 minutos):\n{link}\n\n"
        "Si no has sido tú, ignora este correo: tu contraseña actual sigue funcionando."
    )
    # Estilo alineado con el acento naranja/ambar de la app (ver
    # frontend/css/style.css, --brand-gradient) para que el correo no
    # parezca ajeno al resto del producto.
    html = f"""\
    <div style="font-family: Arial, sans-serif; background-color: #0f172a; padding: 32px; color: #e5e7eb;">
      <div style="max-width: 480px; margin: 0 auto; background-color: #1e293b; border-radius: 16px; padding: 32px; border: 1px solid #334155;">
        <h1 style="color: #ffffff; font-size: 20px; margin: 0 0 16px;">Tracker Oposiciones</h1>
        <p style="font-size: 14px; line-height: 1.6; margin: 0 0 20px;">
          Has solicitado recuperar tu contraseña. Pulsa el siguiente botón para elegir una nueva
          &mdash; el enlace caduca en <strong>15 minutos</strong>.
        </p>
        <a href="{link}"
           style="display: inline-block; background: linear-gradient(135deg, #F97316, #F59E0B);
                  color: #ffffff; text-decoration: none; font-weight: 600; padding: 12px 24px;
                  border-radius: 8px; font-size: 14px;">
          Restablecer contraseña
        </a>
        <p style="font-size: 12px; color: #94a3b8; margin: 24px 0 0;">
          Si no has sido tú, ignora este correo: tu contraseña actual sigue funcionando.
        </p>
      </div>
    </div>
    """
    correo.attach(MIMEText(texto_plano, "plain", "utf-8"))
    correo.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(correo)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        print(f"[olvido-password] fallo enviando el email de recuperacion: {exc}")


@router.post("/olvido-password")
@limiter.limit("5/hour")
async def olvido_password(
    request: Request,
    payload: OlvidoPasswordIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Siempre responde con el mismo mensaje generico, exista o no el email,
    para no revelar que cuentas estan registradas (enumeration attack). El
    envio real va en un BackgroundTask (tras devolver la respuesta) para que
    la latencia de SMTP nunca sea observable comparando "email existe" vs
    "no existe"."""
    usuario = db.query(Usuario).filter(Usuario.email == payload.email).first()

    if usuario is not None:
        token_reset = generar_token_reset(usuario.email)
        link = f"{DOMINIO_APP}/?reset_token={token_reset}"
        background_tasks.add_task(_enviar_email_recuperacion, usuario.email, link)

    return {"mensaje": MENSAJE_GENERICO_OLVIDO}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: Session = Depends(get_db)):
    email = verificar_token_reset(payload.token)
    if email is None:
        raise HTTPException(
            status_code=400, detail="El enlace de recuperación no es válido o ha caducado"
        )

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        raise HTTPException(
            status_code=400, detail="El enlace de recuperación no es válido o ha caducado"
        )

    usuario.hashed_password = get_password_hash(payload.nueva_password)
    db.commit()

    return {"mensaje": "Contraseña actualizada correctamente"}
