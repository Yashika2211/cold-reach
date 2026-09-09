from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    """Cached for FastAPI's DI (Depends(get_redis)) where one event loop lives for
    the whole process lifetime, so reusing a single client/connection is correct."""
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def new_redis_client() -> Redis:
    """Uncached, for Celery task bodies. Each task runs asyncio.run() in a fresh
    event loop; a client cached across those loops holds a connection bound to a
    now-closed loop and breaks on the next task ("Event loop is closed" / "attached
    to a different loop"). Callers must close what this returns when done."""
    return Redis.from_url(get_settings().redis_url, decode_responses=True)
