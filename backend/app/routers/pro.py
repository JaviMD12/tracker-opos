from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.marca import MarcaFisica
from app.models.usuario import Usuario
from app.services.calculo import calcular_puntuacion_completa
from app.services.rutinas import RUTINAS_PRO, TECNICAS_ESTUDIO_PRO
from app.services.security import get_current_user

router = APIRouter(prefix="/api/pro", tags=["pro"])


@router.get("/entrenamiento")
def entrenamiento_especifico(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Detecta la prueba con menor puntuacion del ultimo registro fisico y
    devuelve la rutina especifica del Plan Pro para ese punto debil."""
    ultima_marca = (
        db.query(MarcaFisica)
        .filter(MarcaFisica.usuario_id == current_user.id)
        .order_by(MarcaFisica.fecha.desc(), MarcaFisica.id.desc())
        .first()
    )

    if ultima_marca is None:
        raise HTTPException(
            status_code=404,
            detail="Registra al menos una marca fisica para generar tu entrenamiento especifico.",
        )

    resultado = calcular_puntuacion_completa(
        dominadas=ultima_marca.dominadas,
        sprint_100m=ultima_marca.sprint_100m,
        carrera_1500m=ultima_marca.carrera_1500m,
        natacion_100m=ultima_marca.natacion_100m,
    )

    detalle = resultado["detalle"]
    prueba_debil = min(detalle, key=lambda clave: detalle[clave]["puntos"])

    return {
        "prueba_detectada": prueba_debil,
        "nombre": detalle[prueba_debil]["nombre"],
        "puntos_actuales": detalle[prueba_debil]["puntos"],
        "fecha_analisis": ultima_marca.fecha.isoformat(),
        "rutina": RUTINAS_PRO[prueba_debil],
    }


@router.get("/teorica")
def tecnicas_de_estudio(current_user: Usuario = Depends(get_current_user)):
    """Catalogo de tecnicas de estudio de alto rendimiento del Plan Pro."""
    return {"tecnicas": list(TECNICAS_ESTUDIO_PRO.values())}
