from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pregunta_test import PreguntaTest
from app.models.resultado_simulacro import ResultadoSimulacro
from app.models.usuario import Usuario
from app.schemas import ResultadoSimulacroCreate, SimulacroGenerarIn
from app.services.security import get_current_user

router = APIRouter(prefix="/api/simulacros", tags=["simulacros"])


@router.post("/generar")
def generar_simulacro(
    payload: SimulacroGenerarIn,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    # Banco de preguntas precargado (ver backend/generar_banco.py): ya no se
    # llama a OpenAI en cada peticion, solo un SELECT aleatorio. ORDER BY
    # RANDOM() se compila igual en SQLite y en Postgres, los dos motores que
    # soporta este proyecto (ver app/database.py).
    preguntas_banco = (
        db.query(PreguntaTest)
        .filter(PreguntaTest.tema == payload.tema)
        .order_by(func.random())
        .limit(payload.num_preguntas)
        .all()
    )

    if not preguntas_banco:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No hay preguntas precargadas para el tema '{payload.tema}'. "
                "Genera el banco con backend/generar_banco.py."
            ),
        )

    # Misma forma de JSON que esperaba el frontend cuando esto lo generaba
    # OpenAI en vivo (pregunta/opciones/correcta/explicacion) -- se traduce
    # aqui desde los nombres de columna del modelo para no romper main.js.
    preguntas = [
        {
            "pregunta": p.enunciado,
            "opciones": p.opciones,
            "correcta": p.respuesta_correcta,
            "explicacion": p.justificacion,
        }
        for p in preguntas_banco
    ]

    return {"preguntas": preguntas}


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
