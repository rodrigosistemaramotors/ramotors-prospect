from redis.asyncio import from_url, Redis
from app.config import settings

_redis: Redis | None = None

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = await from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
            health_check_interval=30,
        )
    return _redis

async def close_redis():
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
