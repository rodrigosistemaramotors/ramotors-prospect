from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.security import decodificar_token
from app.models.usuario import UsuarioDashboard
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UsuarioDashboard:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais invalidas",
    )
    try:
        payload = decodificar_token(token)
        if payload.get("tipo") != "access":
            raise cred_exc
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise cred_exc

    result = await db.execute(select(UsuarioDashboard).where(UsuarioDashboard.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.ativo:
        raise cred_exc
    return user

def require_admin(user: UsuarioDashboard = Depends(usuario_atual)) -> UsuarioDashboard:
    if user.role != "ADMIN":
        raise HTTPException(403, "Permissao insuficiente")
    return user

def require_worker(x_worker_key: str = Header(...)) -> bool:
    if x_worker_key != settings.worker_api_key:
        raise HTTPException(401, "Worker key invalida")
    return True
