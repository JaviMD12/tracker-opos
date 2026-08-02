from fastapi import APIRouter, Depends, HTTPException, Request
from google.genai.errors import APIError
from pydantic import BaseModel, Field

from app.models.usuario import Usuario
from app.services.ai_tutor import preguntar_al_tutor
from app.services.rate_limit import limiter
from app.services.security import get_current_user

router = APIRouter(prefix="/api/pro", tags=["chat"])


class ChatMensaje(BaseModel):
    mensaje: str = Field(min_length=1, max_length=1000)


@router.post("/chat")
@limiter.limit("60/hour")
def chat_tutor(
    request: Request, payload: ChatMensaje, current_user: Usuario = Depends(get_current_user)
):
    try:
        respuesta = preguntar_al_tutor(payload.mensaje)
    except APIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"El tutor IA no está disponible ahora mismo: {exc}",
        ) from exc

    return {"respuesta": respuesta}
