import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.models import Anuncio, OptOut
from app.config import settings

REDIS_HASHES_KEY = "ramotors:hashes_recentes"
REDIS_HASHES_TTL_SECONDS = 7 * 24 * 3600

def calcular_hash(fonte: str, url_canonica: str, telefone: str | None) -> str:
    base = f"{fonte}:{url_canonica}:{telefone or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

async def jah_existe(
    redis: Redis,
    db: AsyncSession,
    hash_unico: str,
    telefone: str | None,
) -> tuple[bool, str | None]:
    if await redis.sismember(REDIS_HASHES_KEY, hash_unico):
        return True, "cache_hash"

    q = await db.execute(select(Anuncio.id).where(Anuncio.hash_unico == hash_unico))
    if q.scalar_one_or_none():
        await redis.sadd(REDIS_HASHES_KEY, hash_unico)
        return True, "db_hash"

    if telefone:
        limite = datetime.now(timezone.utc) - timedelta(
            days=settings.bloqueio_telefone_dias
        )
        q2 = await db.execute(
            select(Anuncio.id)
            .where(Anuncio.telefone == telefone)
            .where(Anuncio.capturado_em > limite)
            .limit(1)
        )
        if q2.scalar_one_or_none():
            return True, "telefone_recente"

        q3 = await db.execute(
            select(OptOut.telefone).where(OptOut.telefone == telefone)
        )
        if q3.scalar_one_or_none():
            return True, "opt_out"

    return False, None

async def registrar_hash(redis: Redis, hash_unico: str):
    await redis.sadd(REDIS_HASHES_KEY, hash_unico)
    await redis.expire(REDIS_HASHES_KEY, REDIS_HASHES_TTL_SECONDS)
