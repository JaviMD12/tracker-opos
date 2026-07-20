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

    # El filtro de "plazo vencido" se hace en Python, via Convocatoria.
    # dias_restantes, y no a nivel de SQL: SQLite no conserva el tzinfo en
    # sus columnas DateTime(timezone=True) (las relee "naive"), a diferencia
    # de Postgres -- comparar eso contra un datetime aware de Python
    # directamente en el filtro de la query da resultados inconsistentes
    # entre los dos motores que soporta este proyecto. Se piden bastantes
    # mas de las 20 finales por si hay vencidas entre las mas recientes.
    candidatas = (
        db.query(Convocatoria)
        .order_by(Convocatoria.fecha_publicacion.desc())
        .limit(100)
        .all()
    )
    # Las que no tienen fecha_limite calculable (plazo_dias no detectado, o
    # de antes de que existiera esta columna) se mantienen -- no hay forma
    # de saber si siguen abiertas, no es lo mismo que "vencida".
    vigentes = [c for c in candidatas if c.dias_restantes is None or c.dias_restantes >= 0]
    return vigentes[:20]
