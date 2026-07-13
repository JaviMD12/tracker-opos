from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.convocatoria import Convocatoria
from app.models.usuario import Usuario
from app.schemas import ConvocatoriaOut
from app.services.security import get_current_user

router = APIRouter(prefix="/api/convocatorias", tags=["convocatorias"])


@router.get("", response_model=list[ConvocatoriaOut])
def listar_convocatorias(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    if not current_user.is_pro:
        raise HTTPException(status_code=403, detail="Funcionalidad exclusiva del Plan Pro")

    return (
        db.query(Convocatoria)
        .order_by(Convocatoria.fecha_publicacion.desc())
        .limit(20)
        .all()
    )
