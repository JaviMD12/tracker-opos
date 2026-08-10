import csv
import io
import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.waitlist import Waitlist
from app.schemas import WaitlistCreate
from app.services.rate_limit import limiter

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


def _enviar_email_confirmacion_waitlist(destinatario: str) -> None:
    """Se ejecuta en un BackgroundTask, mismo patron SMTP que
    routers/contacto.py y routers/auth.py::_enviar_email_recuperacion --
    reusa las mismas variables SMTP_* del .env, fallo solo registrado en el
    log del servidor, nunca revelado al usuario."""
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
        print(f"[waitlist] SMTP no configurado, no se confirma por email a {destinatario}.")
        return

    correo = MIMEMultipart()
    correo["From"] = smtp_user
    correo["To"] = destinatario
    correo["Subject"] = "Acceso Prioritario - Tutor IA Oposiciones"
    correo.attach(
        MIMEText(
            "¡Gracias por tu interés!\n\n"
            "Ya estás en la lista de acceso prioritario a la Zona Premium. "
            "En cuanto volvamos a abrir plazas te avisaremos aquí mismo, con "
            "tu primer mes de regalo incluido.\n\n"
            "Un saludo,\nTracker Oposiciones",
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
        print(f"[waitlist] fallo enviando la confirmacion a {destinatario}: {exc}")


@router.post("")
@limiter.limit("5/hour")
def unirse_a_waitlist(
    request: Request,
    payload: WaitlistCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """No exige sesion iniciada: capturar el interes no deberia depender de
    tener ya una cuenta. Email duplicado no es un error -- se trata como
    exito silencioso (misma idea anti-enumeracion que auth.py::olvido_password,
    aunque aqui el riesgo es bajo, es el mismo patron de no exponer detalles
    internos en la respuesta)."""
    ya_existe = db.query(Waitlist).filter(Waitlist.email == payload.email).first()
    if ya_existe is None:
        db.add(Waitlist(email=payload.email))
        db.commit()

    background_tasks.add_task(_enviar_email_confirmacion_waitlist, payload.email)
    return {"mensaje": "Te has apuntado a la lista de espera."}


@router.get("/export.csv")
@limiter.limit("20/hour")
def exportar_waitlist_csv(request: Request, token: str, db: Session = Depends(get_db)):
    """Descarga directa del CSV, protegida por un token compartido en vez de
    login (no hay concepto de "admin" en Usuario, y anadir uno para un unico
    endpoint seria mas complejidad de la que hace falta aqui). El token vive
    en ADMIN_EXPORT_TOKEN (.env), generado aparte (ver instrucciones), nunca
    hardcodeado. secrets.compare_digest evita que una comparacion == normal
    filtre el token por timing attack."""
    token_real = os.environ.get("ADMIN_EXPORT_TOKEN")
    if not token_real or not secrets.compare_digest(token, token_real):
        raise HTTPException(status_code=403, detail="Token invalido")

    filas = db.query(Waitlist).order_by(Waitlist.fecha_registro).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "fecha_registro"])
    for fila in filas:
        writer.writerow([fila.email, fila.fecha_registro])
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=waitlist.csv"},
    )
