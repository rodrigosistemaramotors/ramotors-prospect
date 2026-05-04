from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

def verificar_senha(senha: str, hash_: str) -> bool:
    return pwd_context.verify(senha, hash_)

def criar_token(payload: dict, tipo: str = "access") -> str:
    expira_min = (
        settings.jwt_access_expires_minutes
        if tipo == "access"
        else settings.jwt_refresh_expires_minutes
    )
    to_encode = {
        **payload,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expira_min),
        "tipo": tipo,
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decodificar_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
