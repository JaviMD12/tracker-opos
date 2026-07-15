from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.marca import MarcaFisica
from app.models.sesion_estudio import SesionEstudio
from app.models.usuario import Usuario
from app.schemas import HeatmapDia, SesionEstudioCreate
from app.services.security import get_current_user

router = APIRouter(prefix="/api/actividad", tags=["actividad"])

DIAS_HEATMAP = 60


@router.get("/heatmap", response_model=list[HeatmapDia])
def obtener_heatmap(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=DIAS_HEATMAP - 1)

    conteo_por_dia = defaultdict(int)

    # Actividad fisica: MarcaFisica es el formulario "Registrar marca del
    # dia" realmente activo en la app hoy (no el modelo Workout, que quedo
    # sin uso desde que se revirtio el formulario dinamico de entrenamientos).
    marcas = (
        db.query(MarcaFisica.fecha, func.count(MarcaFisica.id))
        .filter(MarcaFisica.usuario_id == current_user.id, MarcaFisica.fecha >= fecha_inicio)
        .group_by(MarcaFisica.fecha)
        .all()
    )
    for fecha, cantidad in marcas:
        conteo_por_dia[fecha] += cantidad

    # Actividad de estudio: sesiones de trabajo completadas en el Modo
    # Enfoque (Pomodoro), ver POST /sesion-estudio mas abajo.
    sesiones = (
        db.query(SesionEstudio.fecha, func.count(SesionEstudio.id))
        .filter(SesionEstudio.usuario_id == current_user.id, SesionEstudio.fecha >= fecha_inicio)
        .group_by(SesionEstudio.fecha)
        .all()
    )
    for fecha, cantidad in sesiones:
        conteo_por_dia[fecha] += cantidad

    return [
        {
            "date": (fecha_inicio + timedelta(days=i)).isoformat(),
            "intensity": conteo_por_dia.get(fecha_inicio + timedelta(days=i), 0),
        }
        for i in range(DIAS_HEATMAP)
    ]


@router.post("/sesion-estudio")
def crear_sesion_estudio(
    payload: SesionEstudioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    sesion = SesionEstudio(
        usuario_id=current_user.id,
        duracion_minutos=payload.duracion_minutos,
    )
    db.add(sesion)
    db.commit()
    return {"guardado": True}
