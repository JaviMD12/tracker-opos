from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.marca import MarcaFisica
from app.models.usuario import Usuario
from app.schemas import MarcaFisicaCreate, MarcaFisicaCalculada, MarcaFisicaOut
from app.services.calculo import calcular_puntuacion_completa
from app.services.security import get_current_user

router = APIRouter(prefix="/api/marcas", tags=["marcas"])


@router.post("", response_model=MarcaFisicaCalculada)
def crear_marca(
    marca_in: MarcaFisicaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    marca = MarcaFisica(
        fecha=marca_in.fecha or date.today(),
        usuario_id=current_user.id,
        dominadas=marca_in.dominadas,
        sprint_100m=marca_in.sprint_100m,
        carrera_1500m=marca_in.carrera_1500m,
        natacion_100m=marca_in.natacion_100m,
    )
    db.add(marca)
    db.commit()
    db.refresh(marca)

    resultado = calcular_puntuacion_completa(
        dominadas=marca.dominadas,
        sprint_100m=marca.sprint_100m,
        carrera_1500m=marca.carrera_1500m,
        natacion_100m=marca.natacion_100m,
    )

    return MarcaFisicaCalculada(
        marca=MarcaFisicaOut.model_validate(marca),
        detalle=resultado["detalle"],
        nota_global=resultado["nota_global"],
        recomendacion=resultado["recomendacion"],
    )


@router.get("/historial", response_model=list[MarcaFisicaOut])
def historial(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(MarcaFisica)
        .filter(MarcaFisica.usuario_id == current_user.id)
        .order_by(MarcaFisica.fecha.desc(), MarcaFisica.id.desc())
        .all()
    )
