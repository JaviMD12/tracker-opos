import openai
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.convocatoria import Convocatoria
from app.models.usuario import Usuario
from app.services.ai_tutor import generar_plan_estudio_convocatoria
from app.services.security import get_current_user

router = APIRouter(prefix="/api/tutor", tags=["tutor"])


@router.post("/analizar-plaza/{convocatoria_id}")
def analizar_plaza(
    convocatoria_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    convocatoria = db.query(Convocatoria).filter(Convocatoria.id == convocatoria_id).first()
    if not convocatoria:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

    try:
        plan_estudio_md = generar_plan_estudio_convocatoria(
            titulo_plaza=convocatoria.titulo_plaza,
            requisitos_minimos=convocatoria.requisitos_minimos or "No especificados",
        )
    except openai.OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"El tutor IA no esta disponible ahora mismo: {exc}",
        ) from exc

    return {"plan_estudio_md": plan_estudio_md}
