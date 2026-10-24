"""Celery tasks for notifications: sending one email, and the periodic
appointment-reminder sweep (scheduled by celery beat, see celery_app)."""
import app.db.base  # noqa: F401  (registers every model so relationships resolve)
from app.db.session import SessionLocal
from app.services import email_service, notification_service
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="notifications.send_email",
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3,  # mail servers hiccup; try again later
)
def send_email_task(to: str, subject: str, text: str, html_body: str) -> str:
    return email_service.send_email(to, subject, text, html_body)


@celery_app.task(name="notifications.send_appointment_reminders")
def send_appointment_reminders() -> int:
    db = SessionLocal()
    try:
        return notification_service.send_due_reminders(db)
    finally:
        db.close()
