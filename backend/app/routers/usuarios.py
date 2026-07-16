from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas import UsuarioOut
from app.services.security import get_current_user

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


@router.get("/me", response_model=UsuarioOut)
def perfil_usuario(current_user: Usuario = Depends(get_current_user)):
    """Perfil del usuario autenticado (is_pro real, tour_premium_completado...).

    El frontend lo llama al arrancar la sesion (login normal, login con
    Google o token ya guardado) para conocer el estado real de is_pro sin
    depender solo del flag de localStorage."""
    return current_user


@router.post("/tour-completado", response_model=UsuarioOut)
def marcar_tour_completado(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Marca el Tour Guiado de la Zona Premium como visto para no volver a
    mostrarlo nunca mas a este usuario."""
    current_user.tour_premium_completado = True
    db.commit()
    db.refresh(current_user)
    return current_user
