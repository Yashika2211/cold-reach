from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "coldreach",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={},  # populated in Phase 6 with the scheduler tick
)
