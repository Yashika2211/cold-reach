from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis

from app.api.deps import get_current_admin
from app.core.redis import get_redis
from app.services.scheduler import is_globally_paused, set_global_pause

router = APIRouter(prefix="/scheduler", tags=["scheduler"], dependencies=[Depends(get_current_admin)])


class SchedulerStatus(BaseModel):
    paused: bool


@router.get("/status", response_model=SchedulerStatus)
async def scheduler_status(redis: Redis = Depends(get_redis)):
    return SchedulerStatus(paused=await is_globally_paused(redis))


@router.post("/pause", response_model=SchedulerStatus)
async def pause_scheduler(redis: Redis = Depends(get_redis)):
    await set_global_pause(redis, True)
    return SchedulerStatus(paused=True)


@router.post("/resume", response_model=SchedulerStatus)
async def resume_scheduler(redis: Redis = Depends(get_redis)):
    await set_global_pause(redis, False)
    return SchedulerStatus(paused=False)
