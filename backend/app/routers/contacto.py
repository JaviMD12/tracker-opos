import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends

from app.models.usuario import Usuario
from app.schemas import SugerenciaCreate
from app.services.security import get_current_user

router = APIRouter(prefix="/api/contacto", tags=["contacto"])


AUTORRESPUESTA_GRATUITO = (
    "Hemos recibido tu consulta. Debido al alto volumen, las cuentas gratuitas "
    "tienen mayor tiempo de espera. Para dudas de estudio inmediatas, pásate a "
    "Premium y usa el Tutor IA 24/7."
)


def _conexion_smtp_configurada() -> tuple[str, str, str, str] | None:
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        return None
    return smtp_server, smtp_port, smtp_user, smtp_password


def _enviar_email_soporte_premium(asunto: str, mensaje: str, email_usuario: str) -> None:
    """Usuario Premium: se reenvia el mensaje tal cual al admin
    (EMAIL_DESTINO), marcado como prioridad alta. Reply-To apunta al propio
    usuario para poder responderle directamente desde el cliente de correo,
    sin copiar/pegar su email a mano."""
    conexion = _conexion_smtp_configurada()
    email_destino = os.environ.get("EMAIL_DESTINO")
    if conexion is None or not email_destino:
        print(f"[contacto] SMTP no configurado, mensaje PREMIUM perdido de {email_usuario}: {asunto} - {mensaje}")
        return
    smtp_server, smtp_port, smtp_user, smtp_password = conexion

    correo = MIMEMultipart()
    correo["From"] = smtp_user
    correo["To"] = email_destino
    correo["Subject"] = f"[PRIORIDAD ALTA] {asunto} - Tracker Oposiciones"
    correo["Reply-To"] = email_usuario
    correo.attach(
        MIMEText(
            f"Usuario Premium: {email_usuario}\nAsunto: {asunto}\n\n{mensaje}",
            "plain",
            "utf-8",
        )
    )

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(correo)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        print(f"[contacto] fallo enviando el email PREMIUM a admin: {exc}")


def _enviar_autorrespuesta_gratuito(asunto: str, mensaje: str, email_usuario: str) -> None:
    """Usuario gratuito: el mensaje NO se reenvia al admin -- solo se manda
    una autorespuesta al propio usuario. Queda registrado en el log del
    servidor igualmente (aunque no llegue a EMAIL_DESTINO) para no perder
    del todo el rastro de lo que escribio, por si algun dia hace falta
    revisarlo (ej. un bug real reportado desde una cuenta gratuita)."""
    print(f"[contacto] mensaje de cuenta GRATUITA (no reenviado a admin) de {email_usuario}: {asunto} - {mensaje}")

    conexion = _conexion_smtp_configurada()
    if conexion is None:
        print("[contacto] SMTP no configurado, no se manda la autorespuesta al usuario gratuito.")
        return
    smtp_server, smtp_port, smtp_user, smtp_password = conexion

    correo = MIMEMultipart()
    correo["From"] = smtp_user
    correo["To"] = email_usuario
    correo["Subject"] = f"Re: {asunto} - Hemos recibido tu consulta"
    correo.attach(MIMEText(AUTORRESPUESTA_GRATUITO, "plain", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(correo)
    except (smtplib.SMTPException, OSError, ValueError) as exc:
        print(f"[contacto] fallo enviando la autorespuesta al usuario gratuito: {exc}")


@router.post("/enviar")
def enviar_sugerencia(
    payload: SugerenciaCreate,
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_user),
):
    """Envia el mensaje en segundo plano (no bloquea la respuesta al frontend
    esperando a que responda el servidor SMTP). El trato depende de is_pro:
    Premium se reenvia al admin marcado como prioridad alta; gratuito recibe
    solo una autorespuesta automatica, nunca llega al admin."""
    if current_user.is_pro:
        background_tasks.add_task(
            _enviar_email_soporte_premium, payload.asunto, payload.mensaje, current_user.email
        )
    else:
        background_tasks.add_task(
            _enviar_autorrespuesta_gratuito, payload.asunto, payload.mensaje, current_user.email
        )
    return {"enviado": True}
