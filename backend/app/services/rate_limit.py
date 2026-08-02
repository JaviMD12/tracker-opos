"""Limitador de peticiones (slowapi) para blindar endpoints caros en tokens
de IA (Gemini) frente a abuso.

Vive en su propio modulo -- no dentro de main.py -- porque main.py importa
los routers (incluido chat.py) y chat.py necesita importar `limiter` para
poner el decorador @limiter.limit(...) en la ruta: si `limiter` viviera en
main.py, chat.py haria `from app.main import limiter` mientras main.py hace
`from app.routers import chat`, un import circular.
"""

from fastapi import Request
from jose import JWTError, jwt
from slowapi import Limiter

from app.services.security import ALGORITHM, SECRET_KEY


def obtener_identificador_limite(request: Request) -> str:
    """Limita por ID de usuario (claim "sub" del JWT) cuando hay un Bearer
    token valido en la cabecera Authorization; si no hay token o no es
    valido, cae a la IP del cliente.

    Se decodifica el JWT aqui de forma independiente a get_current_user()
    porque slowapi resuelve la clave de limite ANTES de que FastAPI inyecte
    las dependencias de la ruta (Depends(get_current_user) todavia no se ha
    ejecutado en este punto), asi que no hay forma de reutilizar ese
    resultado directamente.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            usuario_id = payload.get("sub")
            if usuario_id:
                return f"usuario:{usuario_id}"
        except JWTError:
            pass  # Token ausente/invalido/caducado: se limita por IP.

    client_ip = request.client.host if request.client else "desconocida"
    return f"ip:{client_ip}"


limiter = Limiter(key_func=obtener_identificador_limite)
