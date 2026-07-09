from fastapi import APIRouter, Depends, HTTPException
from langchain_google_genai._common import GoogleGenerativeAIError
from pydantic import BaseModel, Field

from app.models.usuario import Usuario
from app.services.ai_tutor import preguntar_al_tutor
from app.services.security import get_current_user

router = APIRouter(prefix="/api/pro", tags=["chat"])


class ChatMensaje(BaseModel):
    mensaje: str = Field(min_length=1, max_length=1000)


@router.post("/chat")
def chat_tutor(payload: ChatMensaje, current_user: Usuario = Depends(get_current_user)):
    try:
        respuesta = preguntar_al_tutor(payload.mensaje)
    except GoogleGenerativeAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"El tutor IA no esta disponible ahora mismo: {exc}",
        ) from exc

    return {"respuesta": respuesta}
