from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.simulacro import SimulacroTeorico
from app.models.usuario import Usuario
from app.schemas import SimulacroTeoricoCreate, SimulacroTeoricoCalculado, SimulacroTeoricoOut
from app.services.calculo import calcular_nota_teorica
from app.services.security import get_current_user

router = APIRouter(prefix="/api/teorica", tags=["teorica"])


@router.post("", response_model=SimulacroTeoricoCalculado)
def crear_simulacro(
    simulacro_in: SimulacroTeoricoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    nota = calcular_nota_teorica(simulacro_in.aciertos, simulacro_in.fallos)

    simulacro = SimulacroTeorico(
        fecha=simulacro_in.fecha or date.today(),
        usuario_id=current_user.id,
        aciertos=simulacro_in.aciertos,
        fallos=simulacro_in.fallos,
        blancos=simulacro_in.blancos,
        nota_calculada=nota,
    )
    db.add(simulacro)
    db.commit()
    db.refresh(simulacro)

    return SimulacroTeoricoCalculado(
        simulacro=SimulacroTeoricoOut.model_validate(simulacro),
        nota_calculada=nota,
    )


@router.get("/historial", response_model=list[SimulacroTeoricoOut])
def historial(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    return (
        db.query(SimulacroTeorico)
        .filter(SimulacroTeorico.usuario_id == current_user.id)
        .order_by(SimulacroTeorico.fecha.desc(), SimulacroTeorico.id.desc())
        .all()
    )
