from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import usuario_atual
from app.models import OptOut

router = APIRouter(prefix="/opt-outs", tags=["opt-outs"])

@router.get("")
async def listar(
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    result = await db.execute(select(OptOut).order_by(OptOut.registrado_em.desc()))
    return list(result.scalars())

@router.post("")
async def adicionar(
    telefone: str,
    motivo: str | None = None,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    existe = await db.get(OptOut, telefone)
    if existe:
        return existe
    novo = OptOut(telefone=telefone, motivo=motivo, origem="manual")
    db.add(novo)
    await db.commit()
    return novo
