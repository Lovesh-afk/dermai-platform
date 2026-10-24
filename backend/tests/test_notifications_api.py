"""Phase 12 — notifications, emails, reminders, and the cancel fix."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import register_and_login, slot_at


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.db.session import get_db
    from app.main import app

    return next(app.dependency_overrides[get_db]())


def _setup(client, slug="notif-clinic"):
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = _db()
    try:
        hospital_id = str(create_hospital(db, HospitalCreate(name="Notif", slug=slug), created_by_user_id=None).id)
    finally:
        db.close()
    doctor = register_and_login(client, email=f"doc@{slug}.com", full_name="Arya", hospital_slug=slug)
    doctor_id = client.post("/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": f"L-{slug}"},
                            headers=auth(doctor)).json()["id"]
    patient = register_and_login(client, email=f"pat@{slug}.com", full_name="Lovesh")
    client.post("/api/v1/patients/me", json={}, headers=auth(patient))
    return doctor, doctor_id, patient


def _book(client, patient, doctor_id, index=0, days_ahead=2, reason="Suspicious mole on my arm"):
    resp = client.post("/api/v1/appointments", json={
        "doctor_id": doctor_id, "scheduled_at": slot_at(days_ahead=days_ahead, index=index).isoformat(), "reason": reason,
    }, headers=auth(patient))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _notifications(client, token):
    return client.get("/api/v1/notifications", headers=auth(token)).json()


# --- Appointment events ------------------------------------------------------

def test_booking_notifies_doctor_in_app_and_by_email(client, outbox):
    doctor, doctor_id, patient = _setup(client)
    _book(client, patient, doctor_id)

    n = _notifications(client, doctor)[0]
    assert n["type"] == "appointment.requested" and "Lovesh" in n["body"] and n["link"] == "/doctor"
    assert len(outbox) == 1 and outbox[0]["to"] == "doc@notif-clinic.com"
    assert "Suspicious mole" not in outbox[0]["text"]  # visit reasons are health info: never emailed


def test_confirm_notifies_patient_and_complete_is_in_app_only(client, outbox):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id)
    outbox.clear()

    client.patch(f"/api/v1/appointments/{appt}/status", json={"status": "confirmed"}, headers=auth(doctor))
    assert _notifications(client, patient)[0]["type"] == "appointment.confirmed"
    assert [e["to"] for e in outbox] == ["pat@notif-clinic.com"]
    assert "Dr. Arya confirmed" in outbox[0]["text"]

    outbox.clear()
    client.patch(f"/api/v1/appointments/{appt}/status", json={"status": "completed"}, headers=auth(doctor))
    assert _notifications(client, patient)[0]["type"] == "appointment.completed"
    assert outbox == []


def test_cancellation_notifies_the_other_party(client):
    doctor, doctor_id, patient = _setup(client)
    by_patient = _book(client, patient, doctor_id, index=0)
    by_doctor = _book(client, patient, doctor_id, index=1)

    client.post(f"/api/v1/appointments/{by_patient}/cancel", json={}, headers=auth(patient))
    assert _notifications(client, doctor)[0]["type"] == "appointment.cancelled"

    client.post(f"/api/v1/appointments/{by_doctor}/cancel", json={}, headers=auth(doctor))
    n = _notifications(client, patient)[0]
    assert n["type"] == "appointment.cancelled" and "Dr. Arya cancelled" in n["body"]


# --- The cancel security fix -------------------------------------------------

def test_stranger_cannot_cancel_someone_elses_appointment(client):
    """Regression: before Phase 12 any logged-in user could cancel any appointment by ID."""
    _, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id)
    stranger = register_and_login(client, email="stranger@example.com")

    assert client.post(f"/api/v1/appointments/{appt}/cancel", json={}, headers=auth(stranger)).status_code == 404
    status = client.get("/api/v1/patients/me/appointments", headers=auth(patient)).json()[0]["status"]
    assert status == "pending"


def test_completed_appointment_cannot_be_cancelled(client):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id)
    client.patch(f"/api/v1/appointments/{appt}/status", json={"status": "completed"}, headers=auth(doctor))
    assert client.post(f"/api/v1/appointments/{appt}/cancel", json={}, headers=auth(patient)).status_code == 400


# --- Medical records & AI analysis ---------------------------------------------

def test_new_visit_notes_notify_patient_without_emailing_the_notes(client, outbox):
    doctor, doctor_id, patient = _setup(client)
    _book(client, patient, doctor_id)
    patient_id = client.get("/api/v1/patients/me", headers=auth(patient)).json()["id"]
    outbox.clear()

    client.post("/api/v1/medical-records", json={"patient_id": patient_id, "diagnosis": "Tinea corporis", "notes": "Apply cream"},
                headers=auth(doctor))
    assert _notifications(client, patient)[0]["type"] == "medical_record.created"
    assert len(outbox) == 1
    assert "Tinea" not in outbox[0]["text"] and "cream" not in outbox[0]["text"]


def test_analysis_result_notifies_without_revealing_the_result(client, outbox, monkeypatch):
    import app.services.inference_client as inference_client
    from app.services.prediction_service import run_analysis

    monkeypatch.setattr(inference_client, "predict", lambda *a: {
        "predicted_class": "fungal", "label": "Possible fungal infection", "confidence": 0.9,
        "all_probabilities": {"fungal": 0.9}, "guidance": "g", "disclaimer": "d", "model_name": "m",
        "gradcam_png_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    })
    _, _, patient = _setup(client)
    image = client.post("/api/v1/patients/me/images", files={"file": ("a.jpg", b"img", "image/jpeg")}, headers=auth(patient)).json()
    db = _db()
    try:
        run_analysis(db, uuid.UUID(image["id"]))
    finally:
        db.close()

    assert _notifications(client, patient)[0]["type"] == "analysis.ready"
    assert len(outbox) == 1 and "fungal" not in outbox[0]["text"].lower()


# --- Reminders -------------------------------------------------------------------

def _set_status(client, doctor, appt, status):
    client.patch(f"/api/v1/appointments/{appt}/status", json={"status": status}, headers=auth(doctor))


def test_reminder_sent_once_for_confirmed_appointment_within_24h(client, outbox):
    from app.services.notification_service import send_due_reminders

    doctor, doctor_id, patient = _setup(client)
    soon = _book(client, patient, doctor_id, index=0, days_ahead=1)
    _set_status(client, doctor, soon, "confirmed")
    later = _book(client, patient, doctor_id, index=1, days_ahead=10)
    _set_status(client, doctor, later, "confirmed")
    _book(client, patient, doctor_id, index=2, days_ahead=1)  # still pending: no reminder

    target = slot_at(days_ahead=1, index=0)
    db = _db()
    try:
        assert send_due_reminders(db, now=target - timedelta(hours=20)) == 1
        assert send_due_reminders(db, now=target - timedelta(hours=19)) == 0  # never twice
    finally:
        db.close()
    assert _notifications(client, patient)[0]["type"] == "appointment.reminder"


# --- Bell API ----------------------------------------------------------------------

def test_unread_count_mark_read_and_read_all(client):
    doctor, doctor_id, patient = _setup(client)
    _book(client, patient, doctor_id, index=0)
    _book(client, patient, doctor_id, index=1)

    count = lambda: client.get("/api/v1/notifications/unread-count", headers=auth(doctor)).json()["unread"]
    assert count() == 2
    first = _notifications(client, doctor)[0]
    marked = client.post(f"/api/v1/notifications/{first['id']}/read", headers=auth(doctor)).json()
    assert marked["read_at"] is not None and count() == 1
    assert client.post("/api/v1/notifications/read-all", headers=auth(doctor)).status_code == 204
    assert count() == 0


def test_users_only_see_and_mark_their_own_notifications(client):
    doctor, doctor_id, patient = _setup(client)
    _book(client, patient, doctor_id)
    doctors_note = _notifications(client, doctor)[0]

    assert _notifications(client, patient) == []
    assert client.post(f"/api/v1/notifications/{doctors_note['id']}/read", headers=auth(patient)).status_code == 404
    assert client.get("/api/v1/notifications").status_code == 401


def test_email_queue_down_does_not_break_booking(client, monkeypatch):
    import app.services.notification_service as notification_service

    def broken(*a):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(notification_service, "enqueue_email", broken)
    doctor, doctor_id, patient = _setup(client)
    _book(client, patient, doctor_id)  # asserts 201 inside
    assert _notifications(client, doctor)[0]["type"] == "appointment.requested"  # in-app still saved


# --- Password reset email -------------------------------------------------------------

def test_password_reset_sends_email_with_working_link(client, outbox):
    register_and_login(client, email="forgot@example.com")
    resp = client.post("/api/v1/auth/password-reset/request", json={"email": "forgot@example.com"}).json()

    assert len(outbox) == 1 and outbox[0]["to"] == "forgot@example.com"
    assert f"/reset-password?token={resp['dev_reset_token']}" in outbox[0]["text"]
    token = outbox[0]["text"].split("token=")[1].split()[0]
    ok = client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "new_password": "brandnewpass123"})
    assert ok.status_code == 204


def test_password_reset_unknown_email_sends_nothing_and_production_hides_token(client, outbox, monkeypatch):
    client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert outbox == []

    import app.services.auth_service as auth_service

    monkeypatch.setattr(auth_service.settings, "ENVIRONMENT", "production")
    register_and_login(client, email="prod@example.com")
    resp = client.post("/api/v1/auth/password-reset/request", json={"email": "prod@example.com"}).json()
    assert resp["dev_reset_token"] is None and len(outbox) == 1


# --- Email sender ------------------------------------------------------------------------

def test_console_mode_when_no_smtp_configured(monkeypatch):
    from app.services import email_service

    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "")
    assert email_service.send_email("a@example.com", "Hi", "Body") == "console"


def test_smtp_mode_uses_tls_and_login(monkeypatch):
    from app.services import email_service

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def starttls(self):
            calls.append(("starttls",))
        def login(self, user, password):
            calls.append(("login", user))
        def send_message(self, msg):
            calls.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(email_service.settings, "SMTP_USER", "me@example.com")
    assert email_service.send_email("to@example.com", "Subj", "Body", "<p>Body</p>") == "smtp"
    assert [c[0] for c in calls] == ["connect", "starttls", "login", "send"]  # TLS before the password
