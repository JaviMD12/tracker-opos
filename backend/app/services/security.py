"""Motor de autenticacion: hashing de contraseñas, JWT de sesion, login con
Google (OAuth2/OIDC via Authlib) y tokens firmados de recuperacion de
contraseña (itsdangerous).

SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET se cargan desde
backend/.env (ver app/main.py, load_dotenv()).
"""

import os
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario

SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 semana

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ---------- Login con Google (OAuth2 / OpenID Connect) ----------
# El registro solo guarda la config; no hace ninguna llamada de red hasta que
# se use de verdad (authorize_redirect/authorize_access_token), asi que es
# seguro hacerlo aqui aunque las credenciales aun no esten rellenas en .env.
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# ---------- Recuperacion de contraseña: token firmado de un solo uso ----------
# URLSafeTimedSerializer firma el email + una marca de tiempo con SECRET_KEY;
# verificar_token_reset comprueba la firma Y que no hayan pasado mas de 15 min.
RESET_PASSWORD_SALT = "reset-password"
RESET_PASSWORD_MAX_AGE_SEGUNDOS = 15 * 60
_reset_serializer = URLSafeTimedSerializer(SECRET_KEY)


def generar_token_reset(email: str) -> str:
    return _reset_serializer.dumps(email, salt=RESET_PASSWORD_SALT)


def verificar_token_reset(token: str) -> str | None:
    try:
        return _reset_serializer.loads(
            token, salt=RESET_PASSWORD_SALT, max_age=RESET_PASSWORD_MAX_AGE_SEGUNDOS
        )
    except (BadSignature, SignatureExpired):
        return None


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password_plano: str, password_hasheada: str) -> bool:
    return _pwd_context.verify(password_plano, password_hasheada)


def create_access_token(data: dict) -> str:
    datos = data.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    datos.update({"exp": expira})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Usuario:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = payload.get("sub")
        if usuario_id is None:
            raise credenciales_invalidas
    except JWTError:
        raise credenciales_invalidas from None

    usuario = db.query(Usuario).filter(Usuario.id == int(usuario_id)).first()
    if usuario is None:
        raise credenciales_invalidas
    return usuario
