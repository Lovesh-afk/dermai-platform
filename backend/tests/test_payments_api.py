"""
Phase 13 — consultation-fee payments. Razorpay's HTTP API is faked (no
network in tests), but its signature checks run for real: valid HMAC
signatures are computed exactly as Razorpay computes them.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import register_and_login, slot_at

KEY_ID, KEY_SECRET, WEBHOOK_SECRET = "rzp_test_KEY", "test_secret_123", "whsec_456"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.db.session import get_db
    from app.main import app

    return next(app.dependency_overrides[get_db]())


def _setup(client, fee=500, slug="pay-clinic"):
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = _db()
    try:
        hid = str(create_hospital(db, HospitalCreate(name="Pay", slug=slug), created_by_user_id=None).id)
    finally:
        db.close()
    doctor = register_and_login(client, email=f"doc@{slug}.com", full_name="Arya", hospital_slug=slug)
    body = {"hospital_id": hid, "license_number": f"L-{slug}"}
    if fee is not None:
        body["consultation_fee"] = fee
    doctor_id = client.post("/api/v1/doctors/me", json=body, headers=auth(doctor)).json()["id"]
    patient = register_and_login(client, email=f"pat@{slug}.com", full_name="Lovesh")
    client.post("/api/v1/patients/me", json={}, headers=auth(patient))
    return doctor, doctor_id, patient


def _book(client, patient, doctor_id, index=0, days_ahead=3):
    return client.post("/api/v1/appointments", json={"doctor_id": doctor_id, "scheduled_at": slot_at(days_ahead=days_ahead, index=index).isoformat()},
                       headers=auth(patient))


def _simulate(client, patient, payment_id, outcome="success"):
    return client.post(f"/api/v1/payments/{payment_id}/simulate", json={"outcome": outcome}, headers=auth(patient))


def _types(client, token):
    return [n["type"] for n in client.get("/api/v1/notifications", headers=auth(token)).json()]


@pytest.fixture()
def razorpay(monkeypatch):
    """Switches the app to Razorpay mode and fakes Razorpay's HTTP API."""
    import app.services.payments.providers as providers

    monkeypatch.setattr(providers.settings, "RAZORPAY_KEY_ID", KEY_ID)
    monkeypatch.setattr(providers.settings, "RAZORPAY_KEY_SECRET", KEY_SECRET)
    monkeypatch.setattr(providers.settings, "RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    calls = {"orders": [], "refunds": [], "fail_orders": False, "fail_refunds": False}

    class Resp:
        def __init__(self, code, data):
            self.status_code, self._data, self.text = code, data, json.dumps(data)

        def json(self):
            return self._data

    def fake_post(url, json, auth, timeout):
        assert auth == (KEY_ID, KEY_SECRET)  # HTTP Basic auth with our keys
        if url.endswith("/orders"):
            calls["orders"].append(json)
            return Resp(500, {"error": "down"}) if calls["fail_orders"] else Resp(200, {"id": f"order_T{len(calls['orders'])}"})
        if url.endswith("/refund"):
            calls["refunds"].append((url, json))
            return Resp(500, {"error": "down"}) if calls["fail_refunds"] else Resp(200, {"id": "rfnd_T1"})
        raise AssertionError(url)

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    return calls


def _sign(order_id, payment_id, secret=KEY_SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


# --- Booking ---------------------------------------------------------------------

def test_free_consultation_books_straight_away(client):
    _, doctor_id, patient = _setup(client, fee=None)
    appt = _book(client, patient, doctor_id).json()
    assert appt["status"] == "pending" and appt["payment"] is None


def test_paid_booking_holds_slot_awaiting_payment(client):
    doctor, doctor_id, patient = _setup(client, fee=499.99)
    appt = _book(client, patient, doctor_id).json()
    assert appt["status"] == "awaiting_payment" and appt["hold_expires_at"]
    assert appt["payment"]["amount_paise"] == 49999 and appt["payment"]["status"] == "created"  # integer paise, no float error
    # the doctor isn't bothered with unpaid holds
    assert "appointment.requested" not in _types(client, doctor)
    assert client.get("/api/v1/doctors/me/appointments", headers=auth(doctor)).json() == []
    # and nobody else can grab the held slot
    other = register_and_login(client, email="other@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth(other))
    assert _book(client, other, doctor_id).status_code == 409


def test_simulated_payment_completes_booking(client):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id).json()
    checkout = client.get(f"/api/v1/payments/{appt['payment']['id']}/checkout", headers=auth(patient)).json()
    assert checkout["provider"] == "simulated" and checkout["amount_paise"] == 50000 and checkout["key_id"] is None

    paid = _simulate(client, patient, appt["payment"]["id"]).json()
    assert paid["status"] == "paid" and paid["doctor_name"] == "Arya"
    assert client.get("/api/v1/patients/me/appointments", headers=auth(patient)).json()[0]["status"] == "pending"
    assert "appointment.requested" in _types(client, doctor)
    assert "payment.paid" in _types(client, patient)


def test_failed_payment_can_be_retried(client):
    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    assert _simulate(client, patient, pid, "failure").json()["status"] == "failed"
    assert _simulate(client, patient, pid, "success").json()["status"] == "paid"


# --- Expiry ------------------------------------------------------------------------

def test_unpaid_hold_expires_and_frees_slot(client):
    from app.services.payments.payment_service import expire_unpaid_holds

    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    db = _db()
    try:
        assert expire_unpaid_holds(db, now=datetime.now(timezone.utc) + timedelta(minutes=16)) == 1
    finally:
        db.close()

    appt = client.get("/api/v1/patients/me/appointments", headers=auth(patient)).json()[0]
    assert appt["status"] == "cancelled" and appt["payment"]["status"] == "expired"
    assert "payment.expired" in _types(client, patient)
    assert client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).status_code == 409
    assert _simulate(client, patient, pid).status_code == 400  # too late to pay
    assert _book(client, patient, doctor_id).status_code == 201  # slot is free again


# --- Cancellation & refunds ---------------------------------------------------------

def _paid_booking(client, patient, doctor_id, index=0):
    appt = _book(client, patient, doctor_id, index=index).json()
    _simulate(client, patient, appt["payment"]["id"])
    return appt


def test_doctor_cancelling_gives_full_refund(client):
    doctor, doctor_id, patient = _setup(client)
    appt = _paid_booking(client, patient, doctor_id)
    client.post(f"/api/v1/appointments/{appt['id']}/cancel", json={}, headers=auth(doctor))
    payment = client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]
    assert payment["status"] == "refunded" and "doctor cancelled" in payment["note"]
    assert "payment.refunded" in _types(client, patient)


def test_patient_cancelling_early_gets_refund_late_does_not(client, monkeypatch):
    import app.services.payments.payment_service as payment_service

    _, doctor_id, patient = _setup(client)
    early = _paid_booking(client, patient, doctor_id, index=0)  # 3 days ahead: well before the 24h cutoff
    client.post(f"/api/v1/appointments/{early['id']}/cancel", json={}, headers=auth(patient))

    late = _paid_booking(client, patient, doctor_id, index=1)
    monkeypatch.setattr(payment_service.settings, "REFUND_CUTOFF_HOURS", 24 * 30)  # makes "3 days ahead" count as late
    client.post(f"/api/v1/appointments/{late['id']}/cancel", json={}, headers=auth(patient))

    by_appt = {p["appointment_id"]: p for p in client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()}
    assert by_appt[early["id"]]["status"] == "refunded"
    assert by_appt[late["id"]]["status"] == "paid" and by_appt[late["id"]]["note"].startswith("No refund")


def test_cancelling_unpaid_hold_doesnt_notify_doctor(client):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id).json()
    client.post(f"/api/v1/appointments/{appt['id']}/cancel", json={}, headers=auth(patient))
    assert client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]["status"] == "expired"
    assert "appointment.cancelled" not in _types(client, doctor)


def test_doctor_cannot_confirm_unpaid_booking(client):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id).json()
    resp = client.patch(f"/api/v1/appointments/{appt['id']}/status", json={"status": "confirmed"}, headers=auth(doctor))
    assert resp.status_code == 400


# --- Razorpay -----------------------------------------------------------------------

def test_razorpay_order_and_valid_signature(client, razorpay):
    _, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id).json()
    assert razorpay["orders"][0]["amount"] == 50000 and razorpay["orders"][0]["currency"] == "INR"

    pid = appt["payment"]["id"]
    checkout = client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).json()
    assert checkout["provider"] == "razorpay" and checkout["key_id"] == KEY_ID  # public key only
    assert KEY_SECRET not in json.dumps(checkout)

    body = {"razorpay_order_id": checkout["order_id"], "razorpay_payment_id": "pay_ABC",
            "razorpay_signature": _sign(checkout["order_id"], "pay_ABC")}
    assert client.post(f"/api/v1/payments/{pid}/verify", json=body, headers=auth(patient)).json()["status"] == "paid"


def test_forged_signature_is_rejected(client, razorpay):
    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    order_id = client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).json()["order_id"]

    forged = {"razorpay_order_id": order_id, "razorpay_payment_id": "pay_X", "razorpay_signature": _sign(order_id, "pay_X", "wrong-secret")}
    assert client.post(f"/api/v1/payments/{pid}/verify", json=forged, headers=auth(patient)).status_code == 400
    wrong_order = {"razorpay_order_id": "order_OTHER", "razorpay_payment_id": "pay_X", "razorpay_signature": _sign("order_OTHER", "pay_X")}
    assert client.post(f"/api/v1/payments/{pid}/verify", json=wrong_order, headers=auth(patient)).status_code == 400
    assert client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]["status"] == "created"
    assert _simulate(client, patient, pid).status_code == 400  # no "simulate" shortcut for real payments


def test_order_failure_releases_slot(client, razorpay):
    _, doctor_id, patient = _setup(client)
    razorpay["fail_orders"] = True
    assert _book(client, patient, doctor_id).status_code == 503
    razorpay["fail_orders"] = False
    assert _book(client, patient, doctor_id).status_code == 201  # the slot wasn't left blocked


def test_webhook_marks_paid_once_and_rejects_bad_signatures(client, razorpay):
    doctor, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    order_id = client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).json()["order_id"]
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_WH", "order_id": order_id}}}}).encode()
    good = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()

    assert client.post("/api/v1/payments/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": "bad"}).status_code == 400
    for _ in range(2):  # Razorpay may deliver the same event twice
        assert client.post("/api/v1/payments/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": good}).status_code == 200
    assert client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]["status"] == "paid"
    assert _types(client, doctor).count("appointment.requested") == 1  # notified once, not twice


def test_payment_after_expiry_is_refunded_automatically(client, razorpay):
    from app.services.payments.payment_service import expire_unpaid_holds

    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    order_id = client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).json()["order_id"]
    db = _db()
    try:
        expire_unpaid_holds(db, now=datetime.now(timezone.utc) + timedelta(minutes=16))
    finally:
        db.close()
    raw = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_LATE", "order_id": order_id}}}}).encode()
    sig = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    client.post("/api/v1/payments/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sig})

    payment = client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]
    assert payment["status"] == "refunded" and "after the booking had expired" in payment["note"]
    assert razorpay["refunds"][0][0].endswith("/payments/pay_LATE/refund")


def test_failed_refund_is_recorded_and_cancellation_still_happens(client, razorpay):
    doctor, doctor_id, patient = _setup(client)
    appt = _book(client, patient, doctor_id).json()
    pid = appt["payment"]["id"]
    order_id = client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(patient)).json()["order_id"]
    client.post(f"/api/v1/payments/{pid}/verify", headers=auth(patient), json={
        "razorpay_order_id": order_id, "razorpay_payment_id": "pay_R", "razorpay_signature": _sign(order_id, "pay_R")})

    razorpay["fail_refunds"] = True
    assert client.post(f"/api/v1/appointments/{appt['id']}/cancel", json={}, headers=auth(doctor)).status_code == 200
    assert client.get("/api/v1/patients/me/payments", headers=auth(patient)).json()[0]["status"] == "refund_failed"


# --- Access control & environment ------------------------------------------------------

def test_patients_only_see_their_own_payments(client):
    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    other = register_and_login(client, email="snoop@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth(other))

    assert client.get(f"/api/v1/payments/{pid}/checkout", headers=auth(other)).status_code == 404
    assert _simulate(client, other, pid).status_code == 404
    assert client.get("/api/v1/patients/me/payments", headers=auth(other)).json() == []


def test_simulated_payments_blocked_in_production(client, monkeypatch):
    import app.services.payments.payment_service as payment_service

    _, doctor_id, patient = _setup(client)
    pid = _book(client, patient, doctor_id).json()["payment"]["id"]
    monkeypatch.setattr(payment_service.settings, "ENVIRONMENT", "production")
    assert _simulate(client, patient, pid).status_code == 400
