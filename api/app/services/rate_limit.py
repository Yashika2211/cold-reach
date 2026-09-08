from fastapi import HTTPException, status
from redis.asyncio import Redis

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60


async def check_and_record_login_attempt(redis: Redis, ip: str) -> None:
    """Raise 429 if this IP has hit the login attempt limit; otherwise record one."""
    key = f"login_attempts:{ip}"
    attempts = await redis.incr(key)
    if attempts == 1:
        await redis.expire(key, LOGIN_ATTEMPT_WINDOW_SECONDS)

    if attempts > LOGIN_ATTEMPT_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
        )


async def clear_login_attempts(redis: Redis, ip: str) -> None:
    await redis.delete(f"login_attempts:{ip}")
