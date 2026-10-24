"""Celery app instance. Task modules (notifications, predictions, etc.)
get added here as later phases introduce them — kept empty of actual
tasks in Phase 1 on purpose."""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dermai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.prediction_tasks", "app.tasks.notification_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # If the broker is down, give up quickly instead of blocking the
    # upload request for ages; the image is marked FAILED and can be retried.
    task_publish_retry_policy={"max_retries": 2, "interval_start": 0, "interval_step": 0.5},
    # Periodic jobs, run by the separate "celery_beat" container
    beat_schedule={
        "send-appointment-reminders": {
            "task": "notifications.send_appointment_reminders",
            "schedule": 600.0,  # every 10 minutes
        },
    },
)
