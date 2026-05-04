from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.security import verificar_senha, criar_token, decodificar_token
from app.models.usuario import UsuarioDashboard
from app.schemas.auth import LoginInput, TokenOutput, RefreshInput

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOutput)
async def login(payload: LoginInput, db: AsyncSession = Depends(get_db)):
    q = await db.execute(
        select(UsuarioDashboard).where(UsuarioDashboard.email == payload.email)
    )
    user = q.scalar_one_or_none()
    if not user or not user.ativo or not verificar_senha(payload.senha, user.senha_hash):
        raise HTTPException(401, "Credenciais invalidas")
    return TokenOutput(
        access_token=criar_token({"sub": str(user.id)}, "access"),
        refresh_token=criar_token({"sub": str(user.id)}, "refresh"),
    )

@router.post("/refresh", response_model=TokenOutput)
async def refresh(payload: RefreshInput):
    try:
        data = decodificar_token(payload.refresh_token)
        if data.get("tipo") != "refresh":
            raise HTTPException(401, "Token invalido")
        sub = data["sub"]
    except Exception:
        raise HTTPException(401, "Token invalido")
    return TokenOutput(
        access_token=criar_token({"sub": sub}, "access"),
        refresh_token=criar_token({"sub": sub}, "refresh"),
    )
