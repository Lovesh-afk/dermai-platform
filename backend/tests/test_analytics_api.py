"""
Phase 14 — analytics. Past appointments can't be booked through the API
(booking rejects the past), so history is inserted straight into the
test database, then read back through the real endpoints.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import create_super_admin_and_login, register_and_login

NOW = datetime.now(timezone.utc)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.db.session import get_db
    from app.main import app

    return next(app.dependency_overrides[get_db]())


def _hospital(slug):
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = _db()
    try:
        return str(create_hospital(db, HospitalCreate(name=slug.title(), slug=slug), created_by_user_id=None).id)
    finally:
        db.close()


def _doctor(client, slug, hospital_id, name):
    token = register_and_login(client, email=f"{name.lower()}@{slug}.com", full_name=name, hospital_slug=slug)
    return client.post("/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": f"L-{name}-{slug}"},
                       headers=auth(token)).json()["id"]


def _patient(client, email):
    token = register_and_login(client, email=email)
    return client.post("/api/v1/patients/me", json={}, headers=auth(token)).json()["id"]


def _hospital_admin(client, slug, hospital_id, super_token):
    register_and_login(client, email=f"admin@{slug}.com", hospital_slug=slug)
    client.post(f"/api/v1/admin/platform/hospitals/{hospital_id}/admins", json={"email": f"admin@{slug}.com"}, headers=auth(super_token))
    return client.post("/api/v1/auth/login", json={"email": f"admin@{slug}.com", "password": "strongpass123"}).json()["access_token"]


def _appt(db, hospital_id, doctor_id, patient_id, when, status, payment=None):
    """payment: None, or dict(paid=bool, refunded=bool, amount=int paise)."""
    from app.models.appointment import Appointment, AppointmentStatus
    from app.models.payment import Payment, PaymentStatus

    a = Appointment(hospital_id=uuid.UUID(hospital_id), doctor_id=uuid.UUID(doctor_id), patient_id=uuid.UUID(patient_id),
                    scheduled_at=when, status=AppointmentStatus[status])
    db.add(a)
    db.flush()
    if payment:
        status_ = PaymentStatus.REFUNDED if payment.get("refunded") else PaymentStatus.PAID if payment["paid"] else PaymentStatus.EXPIRED
        db.add(Payment(appointment_id=a.id, patient_id=a.patient_id, hospital_id=a.hospital_id, amount_paise=payment.get("amount", 50000),
                       status=status_, provider="simulated", provider_order_id=f"sim_{uuid.uuid4().hex}",
                       paid_at=when - timedelta(days=1) if payment["paid"] else None,
                       refunded_at=when if payment.get("refunded") else None))
    db.commit()


@pytest.fixture()
def seeded(client):
    """Hospital A: one busy doctor, one idle doctor. Hospital B: one booking."""
    super_token = create_super_admin_and_login(client)
    a_id, b_id = _hospital("alpha"), _hospital("beta")
    busy, idle = _doctor(client, "alpha", a_id, "Busy"), _doctor(client, "alpha", a_id, "Idle")
    b_doc = _doctor(client, "beta", b_id, "Bdoc")
    p1, p2 = _patient(client, "p1@example.com"), _patient(client, "p2@example.com")

    day = lambda n: NOW - timedelta(days=n)  # noqa: E731
    db = _db()
    try:
        _appt(db, a_id, busy, p1, day(5), "COMPLETED", {"paid": True})
        _appt(db, a_id, busy, p2, day(4), "COMPLETED", {"paid": True})
        _appt(db, a_id, busy, p1, day(3), "COMPLETED")
        _appt(db, a_id, busy, p2, day(2), "NO_SHOW")
        _appt(db, a_id, busy, p1, day(2) + timedelta(hours=1), "CANCELLED", {"paid": True, "refunded": True})  # doctor-cancelled, refunded
        _appt(db, a_id, busy, p2, day(1), "CANCELLED", {"paid": False})   # abandoned checkout
        _appt(db, a_id, busy, p1, day(1) + timedelta(hours=2), "AWAITING_PAYMENT")  # live hold: not counted
        _appt(db, a_id, busy, p1, day(40), "COMPLETED", {"paid": True})   # outside a 30-day window
        _appt(db, b_id, b_doc, p2, day(3), "COMPLETED", {"paid": True, "amount": 80000})
    finally:
        db.close()
    return {"super": super_token, "a": a_id, "b": b_id, "admin_a": _hospital_admin(client, "alpha", a_id, super_token)}


def _get(client, token, scope, days=30):
    return client.get(f"/api/v1/admin/{scope}/analytics", params={"days": days}, headers=auth(token))


def test_hospital_totals_and_rates(client, seeded):
    body = _get(client, seeded["admin_a"], "hospital").json()
    t, r = body["totals"], body["rates"]
    assert body["scope"] == "hospital" and body["timezone"] == "Asia/Kolkata"
    assert (t["appointments"], t["completed"], t["no_show"], t["cancelled"]) == (5, 3, 1, 1)
    assert t["abandoned_checkouts"] == 1 and t["active_patients"] == 2
    assert r["no_show_rate"] == 0.25          # 1 / (3 completed + 1 no-show)
    assert r["cancellation_rate"] == 0.2      # 1 / 5 appointments
    assert r["checkout_conversion"] == 0.75   # 3 paid / (3 paid + 1 abandoned)


def test_hospital_revenue_gross_refunds_net(client, seeded):
    rev = _get(client, seeded["admin_a"], "hospital").json()["revenue"]
    assert (rev["gross_paise"], rev["refunded_paise"], rev["net_paise"]) == (150000, 50000, 100000)
    assert (rev["paid_count"], rev["refund_count"]) == (3, 1)


def test_period_filter(client, seeded):
    seven = _get(client, seeded["admin_a"], "hospital", days=7).json()["totals"]["appointments"]
    ninety = _get(client, seeded["admin_a"], "hospital", days=90).json()["totals"]["appointments"]
    assert seven == 5 and ninety == 6  # the 40-day-old visit only shows in the 90-day view


def test_per_doctor_breakdown(client, seeded):
    rows = _get(client, seeded["admin_a"], "hospital").json()["doctors"]
    assert [r["name"] for r in rows] == ["Busy", "Idle"]  # busiest first
    busy = rows[0]
    assert (busy["appointments"], busy["completed"], busy["no_show"], busy["net_revenue_paise"]) == (5, 3, 1, 100000)
    assert rows[1]["appointments"] == 0 and rows[1]["no_show_rate"] is None


def test_daily_series_uses_hospital_time_zone(client):
    """20:00 UTC is 01:30 the next day in Kolkata: it belongs to the later day."""
    super_token = create_super_admin_and_login(client)
    hid = _hospital("tz-clinic")
    doc, pat = _doctor(client, "tz-clinic", hid, "Tz"), _patient(client, "tz@example.com")
    when = (NOW - timedelta(days=3)).replace(hour=20, minute=0, second=0, microsecond=0)
    db = _db()
    try:
        _appt(db, hid, doc, pat, when, "COMPLETED")
    finally:
        db.close()
    admin = _hospital_admin(client, "tz-clinic", hid, super_token)
    daily = _get(client, admin, "hospital").json()["daily"]
    counted_on = [d["date"] for d in daily if d["appointments"]]
    assert counted_on == [(when + timedelta(days=1)).date().isoformat()]


def test_ai_usage_counts_results_by_class(client, seeded):
    from app.models.prediction import Prediction
    from app.models.skin_image import SkinImage, SkinImageStatus

    patient_id = _patient(client, "ai@example.com")
    db = _db()
    try:
        for cls in ["fungal", "fungal", "acne"]:
            img = SkinImage(patient_id=uuid.UUID(patient_id), hospital_id=uuid.UUID(seeded["a"]), storage_key="k",
                            file_url="/u.jpg", content_type="image/jpeg", status=SkinImageStatus.ANALYZED)
            db.add(img)
            db.flush()
            db.add(Prediction(skin_image_id=img.id, hospital_id=img.hospital_id, predicted_class=cls, label="x", confidence=0.9,
                              all_probabilities={}, guidance="g", disclaimer="d", gradcam_storage_key="h", gradcam_url="/h.png", model_name="m"))
        db.add(SkinImage(patient_id=uuid.UUID(patient_id), hospital_id=uuid.UUID(seeded["a"]), storage_key="k2",
                         file_url="/v.jpg", content_type="image/jpeg", status=SkinImageStatus.FAILED))
        db.commit()
    finally:
        db.close()
    ai = _get(client, seeded["admin_a"], "hospital").json()["ai"]
    assert (ai["photos_uploaded"], ai["analyzed"], ai["failed"]) == (4, 3, 1)
    assert ai["by_class"] == {"fungal": 2, "acne": 1}


def test_hospital_admin_sees_only_their_hospital(client, seeded):
    body = _get(client, seeded["admin_a"], "hospital").json()
    assert body["totals"]["appointments"] == 5        # hospital B's visit isn't included
    assert body["revenue"]["gross_paise"] == 150000   # nor its ₹800
    assert _get(client, seeded["admin_a"], "platform").status_code == 403


def test_platform_view_covers_every_hospital(client, seeded):
    body = _get(client, seeded["super"], "platform").json()
    assert body["scope"] == "platform" and body["totals"]["appointments"] == 6
    assert body["revenue"]["net_paise"] == 100000 + 80000
    rows = {h["name"]: h for h in body["hospitals"]}
    assert rows["Alpha"]["appointments"] == 5 and rows["Alpha"]["doctors"] == 2
    assert rows["Beta"]["net_revenue_paise"] == 80000


def test_access_rules_and_validation(client, seeded):
    patient = register_and_login(client, email="nosy@example.com")
    assert _get(client, patient, "hospital").status_code == 403
    assert _get(client, seeded["super"], "hospital").status_code == 400  # super admin has no single hospital
    assert _get(client, seeded["admin_a"], "hospital", days=0).status_code == 422
    assert _get(client, seeded["admin_a"], "hospital", days=366).status_code == 422


def test_empty_hospital_gives_zeros_not_fake_percentages(client):
    super_token = create_super_admin_and_login(client)
    hid = _hospital("empty-clinic")
    body = _get(client, _hospital_admin(client, "empty-clinic", hid, super_token), "hospital", days=7).json()
    assert body["totals"]["appointments"] == 0 and body["revenue"]["net_paise"] == 0
    assert body["rates"] == {"no_show_rate": None, "cancellation_rate": None, "checkout_conversion": None}
    assert len(body["daily"]) == 8  # one point per day, including today
