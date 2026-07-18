import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends

from app.models.usuario import Usuario
from app.schemas import SugerenciaCreate
from app.services.security import get_current_user

router = APIRouter(prefix="/api/contacto", tags=["contacto"])


def _enviar_email_sugerencia(mensaje: str, email_usuario: str) -> None:
    """Se ejecuta en un BackgroundTask, ya con la respuesta HTTP enviada al
    usuario: si falla, no hay forma de avisarle (ni falta que hace, es un
    formulario de sugerencias, no un flujo critico). El fallo se registra en
    el log del servidor para poder depurarlo, mismo patron que
    routers/auth.py::olvido_password con su webhook de recuperacion."""
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    email_destino = os.environ.get("EMAIL_DESTINO")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password, email_destino]):
        print("[contacto] SMTP no configurado en .env, no se envia el email de sugerencia.")
        return

    correo = MIMEMultipart()
    correo["From"] = smtp_user
    correo["To"] = email_destino
    correo["Subject"] = "Nueva sugerencia - Tracker Oposiciones"
    correo.attach(
        MIMEText(f"Enviado por: {email_usuario}\n\n{mensaje}", "plain", "utf-8")
    )

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(correo)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        print(f"[contacto] fallo enviando el email de sugerencia: {exc}")


@router.post("/enviar")
def enviar_sugerencia(
    payload: SugerenciaCreate,
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
):
    """Recibe una sugerencia del usuario y la envia por email a EMAIL_DESTINO
    en segundo plano, para no bloquear la respuesta al frontend esperando a
    que responda el servidor SMTP."""
    background_tasks.add_task(
        _enviar_email_sugerencia, payload.mensaje, current_user.email
    )
    return {"enviado": True}
