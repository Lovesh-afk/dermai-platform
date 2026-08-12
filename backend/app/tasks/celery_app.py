"""Celery app instance. Task modules (notifications, predictions, etc.)
get added here as later phases introduce them — kept empty of actual
tasks in Phase 1 on purpose."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dermai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
