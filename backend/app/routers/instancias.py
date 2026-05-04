from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import usuario_atual, require_worker
from app.models import InstanciaWhatsapp, StatusInstancia

router = APIRouter(prefix="/instancias-whatsapp", tags=["instancias"])

@router.get("")
async def listar(
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    result = await db.execute(select(InstanciaWhatsapp))
    return list(result.scalars())

@router.post("/{inst_id}/pausar")
async def pausar(
    inst_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    inst = await db.get(InstanciaWhatsapp, inst_id)
    if not inst:
        raise HTTPException(404)
    inst.status = StatusInstancia.PAUSADA
    await db.commit()
    return inst

@router.post("/{inst_id}/ativar")
async def ativar(
    inst_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    inst = await db.get(InstanciaWhatsapp, inst_id)
    if not inst:
        raise HTTPException(404)
    inst.status = StatusInstancia.ATIVA
    await db.commit()
    return inst

@router.post("/por-evolution-id/{evolution_id}/pausar")
async def pausar_por_evolution_id(
    evolution_id: str,
    db: AsyncSession = Depends(get_db),
    _w = Depends(require_worker),
):
    q = await db.execute(
        select(InstanciaWhatsapp).where(
            InstanciaWhatsapp.evolution_instance_id == evolution_id
        )
    )
    inst = q.scalar_one_or_none()
    if not inst:
        raise HTTPException(404, "Instancia nao encontrada")
    inst.status = StatusInstancia.PAUSADA
    await db.commit()
    return {"ok": True, "instancia_id": inst.id, "novo_status": "PAUSADA"}
