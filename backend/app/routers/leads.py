from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import usuario_atual
from app.models import Lead, StatusFunil

router = APIRouter(prefix="/leads", tags=["leads"])

@router.get("")
async def listar(
    status: StatusFunil | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    q = select(Lead).order_by(Lead.created_at.desc())
    if status:
        q = q.where(Lead.status_funil == status)
    result = await db.execute(q.limit(limit))
    return list(result.scalars())

@router.get("/{lead_id}")
async def detalhe(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404)
    return lead

@router.patch("/{lead_id}")
async def atualizar(
    lead_id: int,
    status_funil: StatusFunil | None = None,
    atribuido_a: int | None = None,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404)
    if status_funil:
        lead.status_funil = status_funil
    if atribuido_a is not None:
        lead.atribuido_a = atribuido_a
    await db.commit()
    return lead
