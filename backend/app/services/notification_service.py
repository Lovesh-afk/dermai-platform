"""
Creates notifications and queues their emails. One function per event,
so every message the app sends is defined in one place.

Two rules apply to every event:
  1. Notifying must never break the action that triggered it. If the
     email queue is down, the booking still succeeds and the in-app
     notification is still saved.
  2. Emails carry no medical details (no diagnoses, AI results, visit
     notes or visit reasons), because email isn't a secure channel.
     They say what happened and link to the app, where the details
     sit behind a login.
"""
import html
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User

REMINDER_WINDOW = timedelta(hours=24)


# --- Core ----------------------------------------------------------------

def enqueue_email(to: str, subject: str, text: str, html_body: str) -> None:
    """Hands the email to Celery. Its own function so tests can replace it."""
    from app.tasks.notification_tasks import send_email_task

    send_email_task.delay(to, subject, text, html_body)


def notify(db: Session, user_id: uuid.UUID, type: str, title: str, body: str,
           link: str | None = None, email_text: str | None = None) -> Notification:
    """Saves an in-app notification; also emails the user when
    `email_text` is given (callers must keep it free of medical details)."""
    notification = Notification(user_id=user_id, type=type, title=title, body=body, link=link)
    db.add(notification)
    db.commit()

    if email_text:
        user = db.get(User, user_id)
        if user and user.is_active:
            try:
                text, html_body = _render_email(user.full_name, email_text, link)
                enqueue_email(user.email, f"DermAI: {title}", text, html_body)
            except Exception as e:  # rule 1: never fail the original action
                logger.error("email_enqueue_failed", user_id=str(user_id), type=type, error=str(e))
    return notification


def _render_email(name: str, message: str, link: str | None) -> tuple[str, str]:
    url = f"{settings.FRONTEND_URL}{link}" if link else settings.FRONTEND_URL
    footer = "You're receiving this because you have a DermAI account."
    text = f"Hi {name},\n\n{message}\n\nOpen DermAI: {url}\n\n— The DermAI team\n{footer}"
    e = html.escape  # user-supplied names must never become HTML
    html_body = (
        f'<div style="font-family:sans-serif;max-width:520px;color:#20281F">'
        f"<p>Hi {e(name)},</p><p>{e(message)}</p>"
        f'<p><a href="{e(url)}" style="background:#2F5D50;color:#fff;padding:10px 18px;'
        f'border-radius:999px;text-decoration:none;display:inline-block">Open DermAI</a></p>'
        f'<p style="color:#4B564A;font-size:12px">{e(footer)}</p></div>'
    )
    return text, html_body


def _when(db: Session, appointment: Appointment) -> str:
    """Appointment time in the hospital's time zone, e.g. "Mon 26 Oct, 10:30 (Asia/Kolkata)"."""
    from app.services.scheduling_service import _utc, hospital_zone

    doctor = db.get(Doctor, appointment.doctor_id)
    zone = hospital_zone(db, doctor)
    return f"{_utc(appointment.scheduled_at).astimezone(zone):%a %d %b, %H:%M} ({zone.key})"


def _people(db: Session, appointment: Appointment) -> tuple[User, Doctor]:
    patient = db.get(Patient, appointment.patient_id)
    return db.get(User, patient.user_id), db.get(Doctor, appointment.doctor_id)


def _dr(doctor: Doctor) -> str:
    return f"Dr. {doctor.full_name}" if doctor.full_name else "Your doctor"


# --- Events ----------------------------------------------------------------

def appointment_booked(db: Session, appointment: Appointment) -> None:
    patient_user, doctor = _people(db, appointment)
    when = _when(db, appointment)
    msg = f"{patient_user.full_name} requested an appointment on {when}."
    notify(db, doctor.user_id, "appointment.requested", "New appointment request", msg, "/doctor",
           email_text=msg + " Please confirm it in your queue.")


def appointment_status_changed(db: Session, appointment: Appointment) -> None:
    patient_user, doctor = _people(db, appointment)
    when = _when(db, appointment)
    if appointment.status == AppointmentStatus.CONFIRMED:
        msg = f"{_dr(doctor)} confirmed your appointment on {when}."
        notify(db, patient_user.id, "appointment.confirmed", "Appointment confirmed", msg, "/patient/appointments", email_text=msg)
    elif appointment.status == AppointmentStatus.COMPLETED:
        notify(db, patient_user.id, "appointment.completed", "Visit completed",
               f"Your visit with {_dr(doctor)} on {when} is complete.", "/patient/appointments")
    elif appointment.status == AppointmentStatus.NO_SHOW:
        notify(db, patient_user.id, "appointment.no_show", "Missed appointment",
               f"You were marked as missing your appointment with {_dr(doctor)} on {when}. You can book a new time.",
               "/patient/doctors")


def appointment_cancelled(db: Session, appointment: Appointment, cancelled_by: User) -> None:
    patient_user, doctor = _people(db, appointment)
    when = _when(db, appointment)
    if cancelled_by.id == patient_user.id:
        msg = f"{patient_user.full_name} cancelled their appointment on {when}."
        notify(db, doctor.user_id, "appointment.cancelled", "Appointment cancelled", msg, "/doctor", email_text=msg)
    else:
        msg = f"{_dr(doctor)} cancelled your appointment on {when}. Please book another time."
        notify(db, patient_user.id, "appointment.cancelled", "Appointment cancelled", msg, "/patient/doctors", email_text=msg)


def medical_record_added(db: Session, patient: Patient, doctor: Doctor) -> None:
    notify(db, patient.user_id, "medical_record.created", "New visit notes",
           f"{_dr(doctor)} added notes to your medical record.", "/patient/records",
           email_text=f"{_dr(doctor)} added notes to your medical record. Log in to read them.")


def analysis_finished(db: Session, patient_user_id: uuid.UUID, succeeded: bool) -> None:
    if succeeded:
        notify(db, patient_user_id, "analysis.ready", "Photo analysis ready",
               "Your skin photo analysis is ready.", "/patient/images",
               email_text="Your skin photo analysis is ready. Log in to see the result.")
    else:
        notify(db, patient_user_id, "analysis.failed", "Photo analysis failed",
               "We couldn't analyse your photo. You can retry it from the Skin photos page.", "/patient/images")


def send_due_reminders(db: Session, now: datetime | None = None) -> int:
    """Reminds patients of confirmed appointments in the next 24 hours.
    Runs every 10 minutes; reminder_sent_at makes it safe to run any
    number of times without sending duplicates. Returns how many were sent."""
    from app.services.scheduling_service import _utc

    now = now or datetime.now(timezone.utc)
    candidates = db.execute(
        select(Appointment).where(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.reminder_sent_at.is_(None),
            Appointment.scheduled_at >= now,
        )
    ).scalars().all()
    sent = 0
    for appt in candidates:
        if _utc(appt.scheduled_at) > now + REMINDER_WINDOW:
            continue
        appt.reminder_sent_at = now
        db.commit()  # mark first: if notifying crashes, we skip rather than spam
        patient_user, doctor = _people(db, appt)
        msg = f"Reminder: your appointment with {_dr(doctor)} is on {_when(db, appt)}."
        notify(db, patient_user.id, "appointment.reminder", "Appointment tomorrow", msg, "/patient/appointments", email_text=msg)
        sent += 1
    return sent


# --- Reading notifications ---------------------------------------------------

def list_for_user(db: Session, user: User, limit: int = 20) -> list[Notification]:
    return list(db.execute(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(limit)
    ).scalars().all())


def unread_count(db: Session, user: User) -> int:
    return db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    ).scalar_one()


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> Notification:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:  # someone else's looks exactly like a missing one
        raise NotFoundError("Notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)
    return n


def mark_all_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
