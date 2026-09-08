from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_USER_KEY, get_current_admin
from app.core.redis import get_redis
from app.core.security import verify_password
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.auth import LoginRequest, MeResponse
from app.services.rate_limit import check_and_record_login_attempt, clear_login_attempts

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    client_ip = request.client.host if request.client else "unknown"
    await check_and_record_login_attempt(redis, client_ip)

    result = await db.execute(select(AdminUser).where(AdminUser.email == payload.email))
    admin = result.scalar_one_or_none()

    if admin is None or not admin.is_active or not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await clear_login_attempts(redis, client_ip)
    request.session[SESSION_USER_KEY] = str(admin.id)
    return MeResponse(id=str(admin.id), email=admin.email)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"status": "ok"}


@router.get("/me", response_model=MeResponse)
async def me(admin: AdminUser = Depends(get_current_admin)):
    return MeResponse(id=str(admin.id), email=admin.email)
