from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.database import get_db
from app.redis_client import get_redis
from app.deps import usuario_atual, require_worker
from app.models import Anuncio, StatusContato
from app.schemas.anuncio import (
    AnuncioRead, AnuncioLote, AnuncioStatusUpdate
)
from app.services.deduplicacao import jah_existe, registrar_hash

router = APIRouter(prefix="/anuncios", tags=["anuncios"])

@router.get("", response_model=list[AnuncioRead])
async def listar(
    fonte: str | None = None,
    cidade: str | None = None,
    status: StatusContato | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    q = select(Anuncio).order_by(Anuncio.capturado_em.desc())
    if fonte:
        q = q.where(Anuncio.fonte == fonte)
    if cidade:
        q = q.where(Anuncio.cidade == cidade)
    if status:
        q = q.where(Anuncio.status_contato == status)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars())

@router.get("/{anuncio_id}", response_model=AnuncioRead)
async def detalhe(
    anuncio_id: int,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    a = await db.get(Anuncio, anuncio_id)
    if not a:
        raise HTTPException(404, "Nao encontrado")
    return a

@router.patch("/{anuncio_id}/status", response_model=AnuncioRead)
async def atualizar_status(
    anuncio_id: int,
    payload: AnuncioStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _u = Depends(usuario_atual),
):
    a = await db.get(Anuncio, anuncio_id)
    if not a:
        raise HTTPException(404)
    a.status_contato = payload.status_contato
    await db.commit()
    await db.refresh(a)
    return a

@router.post("/lote", status_code=201)
async def receber_lote(
    payload: AnuncioLote,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _w = Depends(require_worker),
):
    novos_ids = []
    descartados = 0
    motivos: dict[str, int] = {}
    for a in payload.anuncios:
        existe, motivo = await jah_existe(redis, db, a.hash_unico, a.telefone)
        if existe:
            descartados += 1
            motivos[motivo or "desconhecido"] = motivos.get(motivo or "desconhecido", 0) + 1
            continue
        novo = Anuncio(**a.model_dump())
        db.add(novo)
        await db.flush()
        await registrar_hash(redis, a.hash_unico)
        novos_ids.append(novo.id)
    await db.commit()
    return {
        "novos": len(novos_ids),
        "descartados": descartados,
        "motivos_descarte": motivos,
        "ids": novos_ids,
    }
