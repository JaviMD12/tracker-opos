from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.flashcard import Flashcard
from app.models.progreso_flashcard import ProgresoFlashcard
from app.models.usuario import Usuario
from app.schemas import FlashcardReviewIn
from app.services.security import get_current_user
from app.services.srs import FACILIDAD_INICIAL, calcular_siguiente_repaso

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])

# Tope de una sesion de repaso, mismo criterio que un "daily review limit" de
# Anki -- evita que un tema con miles de tarjetas vencidas a la vez devuelva
# de golpe una cola inmanejable en el frontend.
LIMITE_SESION = 30


@router.get("/due")
def obtener_flashcards_pendientes(
    tema: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    # LEFT JOIN contra el progreso de ESTE usuario: una flashcard sin fila de
    # progreso (nunca repasada) cuenta como pendiente desde el primer
    # momento, igual que una cuya fecha_proximo_repaso ya paso.
    filas = (
        db.query(Flashcard)
        .outerjoin(
            ProgresoFlashcard,
            (ProgresoFlashcard.flashcard_id == Flashcard.id)
            & (ProgresoFlashcard.usuario_id == current_user.id),
        )
        .filter(Flashcard.tema == tema)
        .filter(
            (ProgresoFlashcard.id.is_(None))
            | (ProgresoFlashcard.fecha_proximo_repaso <= date.today())
        )
        .order_by(func.random())
        .limit(LIMITE_SESION)
        .all()
    )

    return {
        "flashcards": [
            {"id": f.id, "tema": f.tema, "pregunta": f.pregunta, "respuesta": f.respuesta}
            for f in filas
        ]
    }


@router.post("/review")
def revisar_flashcard(
    payload: FlashcardReviewIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    flashcard = db.query(Flashcard).filter(Flashcard.id == payload.flashcard_id).first()
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard no encontrada")

    progreso = (
        db.query(ProgresoFlashcard)
        .filter(
            ProgresoFlashcard.usuario_id == current_user.id,
            ProgresoFlashcard.flashcard_id == payload.flashcard_id,
        )
        .first()
    )
    if not progreso:
        progreso = ProgresoFlashcard(
            usuario_id=current_user.id,
            flashcard_id=payload.flashcard_id,
            intervalo_dias=1,
            facilidad=FACILIDAD_INICIAL,
        )
        db.add(progreso)

    nuevo_intervalo, nueva_facilidad, nueva_fecha = calcular_siguiente_repaso(
        progreso.intervalo_dias, progreso.facilidad, payload.resultado
    )
    progreso.intervalo_dias = nuevo_intervalo
    progreso.facilidad = nueva_facilidad
    progreso.fecha_proximo_repaso = nueva_fecha

    db.commit()
    return {"intervalo_dias": nuevo_intervalo, "fecha_proximo_repaso": nueva_fecha.isoformat()}
