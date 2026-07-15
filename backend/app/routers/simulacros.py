import json

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resultado_simulacro import ResultadoSimulacro
from app.models.usuario import Usuario
from app.schemas import ResultadoSimulacroCreate, SimulacroGenerarIn
from app.services.ai_tutor import generar_simulacro_test
from app.services.security import get_current_user

router = APIRouter(prefix="/api/simulacros", tags=["simulacros"])


@router.post("/generar")
def generar_simulacro(
    payload: SimulacroGenerarIn,
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    try:
        examen = generar_simulacro_test(payload.tema, payload.num_preguntas)
    except (OpenAIError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo generar el simulacro: {exc}",
        ) from exc

    return examen


@router.post("/guardar")
def guardar_resultado_simulacro(
    payload: ResultadoSimulacroCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    resultado = ResultadoSimulacro(
        usuario_id=current_user.id,
        tema=payload.tema,
        aciertos=payload.aciertos,
        total_preguntas=payload.total_preguntas,
    )
    db.add(resultado)
    db.commit()
    return {"guardado": True}
