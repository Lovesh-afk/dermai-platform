"""Phase 11 — working hours, bookable slots, and booking validation."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import create_super_admin_and_login, register_and_login, slot_at

KOLKATA = ZoneInfo("Asia/Kolkata")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _setup(client, slug="sched-clinic"):
    """A hospital, a doctor (returns their token + id) and a patient token."""
    from app.db.session import get_db
    from app.main import app
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = next(app.dependency_overrides[get_db]())
    try:
        hospital_id = str(create_hospital(db, HospitalCreate(name="Sched", slug=slug), created_by_user_id=None).id)
    finally:
        db.close()
    doctor_token = register_and_login(client, email=f"doc@{slug}.com", full_name="Dr Sched", hospital_slug=slug)
    doctor_id = client.post("/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": f"L-{slug}"},
                            headers=auth(doctor_token)).json()["id"]
    patient_token = register_and_login(client, email=f"pat@{slug}.com")
    client.post("/api/v1/patients/me", json={}, headers=auth(patient_token))
    return hospital_id, doctor_token, doctor_id, patient_token


def _book(client, token, doctor_id, when):
    when = when.isoformat() if isinstance(when, datetime) else when
    return client.post("/api/v1/appointments", json={"doctor_id": doctor_id, "scheduled_at": when}, headers=auth(token))


def _slots(client, doctor_id, days=14):
    return client.get(f"/api/v1/doctors/{doctor_id}/slots", params={"days": days}).json()


def _next_weekday(target_weekday, at: time, min_days=1):
    day = datetime.now(KOLKATA).date() + timedelta(days=min_days)
    while day.weekday() != target_weekday:
        day += timedelta(days=1)
    return datetime.combine(day, at, tzinfo=KOLKATA)


# --- Default hours & slot generation ---------------------------------

def test_default_hours_give_weekday_slots_9_to_5(client):
    _, _, doctor_id, _ = _setup(client)
    body = _slots(client, doctor_id)
    assert body["timezone"] == "Asia/Kolkata" and body["slot_minutes"] == 30

    for day in body["days"]:
        weekday = datetime.fromisoformat(day["date"]).weekday()
        if weekday >= 5:
            assert day["slots"] == []  # no weekend slots by default
    full_day = next(d for d in body["days"][1:] if d["slots"])  # tomorrow onwards: not cut short by "now"
    labels = [s["label"] for s in full_day["slots"]]
    assert labels[0] == "09:00" and labels[-1] == "16:30" and len(labels) == 16
    # 09:00 in Kolkata (UTC+5:30) is 03:30 UTC
    assert datetime.fromisoformat(full_day["slots"][0]["start"]).astimezone(timezone.utc).strftime("%H:%M") == "03:30"


def test_booked_slot_disappears_and_cancel_frees_it(client):
    _, _, doctor_id, patient = _setup(client)
    when = slot_at(days_ahead=2, index=3)
    appt = _book(client, patient, doctor_id, when)
    assert appt.status_code == 201

    starts = {s["start"] for d in _slots(client, doctor_id)["days"] for s in d["slots"]}
    assert not any(datetime.fromisoformat(s) == when for s in starts)

    client.post(f"/api/v1/appointments/{appt.json()['id']}/cancel", json={}, headers=auth(patient))
    starts = {s["start"] for d in _slots(client, doctor_id)["days"] for s in d["slots"]}
    assert any(datetime.fromisoformat(s) == when for s in starts)


def test_not_accepting_doctor_has_no_slots(client):
    _, doctor_token, doctor_id, _ = _setup(client)
    client.patch("/api/v1/doctors/me", json={"is_accepting_appointments": False}, headers=auth(doctor_token))
    assert _slots(client, doctor_id)["days"] == []


# --- Booking validation -----------------------------------------------

@pytest.mark.parametrize("when_fn, case", [
    (lambda: _next_weekday(5, time(10, 0)), "weekend"),
    (lambda: _next_weekday(1, time(20, 0)), "after hours"),
    (lambda: _next_weekday(1, time(9, 10)), "not on a slot boundary"),
    (lambda: datetime.now(timezone.utc) - timedelta(days=1), "in the past"),
])
def test_invalid_times_are_rejected(client, when_fn, case):
    _, _, doctor_id, patient = _setup(client)
    resp = _book(client, patient, doctor_id, when_fn())
    assert resp.status_code == 400, case


def test_double_booking_returns_409(client):
    _, _, doctor_id, patient = _setup(client)
    when = slot_at(index=5)
    assert _book(client, patient, doctor_id, when).status_code == 201
    other = register_and_login(client, email="second@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth(other))
    assert _book(client, other, doctor_id, when).status_code == 409


def test_database_blocks_double_booking_even_if_app_check_is_bypassed(client, monkeypatch):
    """Simulates two requests racing past the app-level check at the same
    moment: the unique index must still reject the second insert."""
    import app.services.appointment_service as appointment_service

    monkeypatch.setattr(appointment_service, "_slot_is_taken", lambda *a: False)
    _, _, doctor_id, patient = _setup(client)
    when = slot_at(index=6)
    assert _book(client, patient, doctor_id, when).status_code == 201
    assert _book(client, patient, doctor_id, when).status_code == 409


def test_local_offset_booking_is_stored_in_utc(client):
    _, _, doctor_id, patient = _setup(client)
    local = slot_at(index=2).astimezone(KOLKATA)  # e.g. 10:00+05:30
    resp = _book(client, patient, doctor_id, local.isoformat())
    assert resp.status_code == 201
    stored = datetime.fromisoformat(resp.json()["scheduled_at"].replace("Z", "+00:00"))
    assert stored.replace(tzinfo=stored.tzinfo or timezone.utc) == local


# --- Custom working hours ---------------------------------------------

def test_doctor_sets_custom_hours(client):
    _, doctor_token, doctor_id, patient = _setup(client)
    resp = client.put("/api/v1/doctors/me/availability",
                      json={"blocks": [{"weekday": 5, "start_time": "10:00", "end_time": "12:00"}]}, headers=auth(doctor_token))
    assert resp.status_code == 200
    assert resp.json()["is_default"] is False

    days_with_slots = [d for d in _slots(client, doctor_id)["days"] if d["slots"]]
    assert days_with_slots and all(datetime.fromisoformat(d["date"]).weekday() == 5 for d in days_with_slots)
    assert [s["label"] for s in days_with_slots[0]["slots"]] == ["10:00", "10:30", "11:00", "11:30"]

    assert _book(client, patient, doctor_id, slot_at(index=0)).status_code == 400  # weekday: now closed
    assert _book(client, patient, doctor_id, _next_weekday(5, time(10, 30))).status_code == 201


def test_empty_schedule_restores_default_hours(client):
    _, doctor_token, _, _ = _setup(client)
    client.put("/api/v1/doctors/me/availability", json={"blocks": [{"weekday": 0, "start_time": "10:00", "end_time": "11:00"}]}, headers=auth(doctor_token))
    resp = client.put("/api/v1/doctors/me/availability", json={"blocks": []}, headers=auth(doctor_token))
    assert resp.json()["is_default"] is True and len(resp.json()["blocks"]) == 5


@pytest.mark.parametrize("blocks", [
    [{"weekday": 0, "start_time": "12:00", "end_time": "09:00"}],            # ends before it starts
    [{"weekday": 0, "start_time": "09:15", "end_time": "12:00"}],            # not on :00/:30
    [{"weekday": 7, "start_time": "09:00", "end_time": "12:00"}],            # no such weekday
    [{"weekday": 0, "start_time": "09:00", "end_time": "12:00"},
     {"weekday": 0, "start_time": "11:00", "end_time": "14:00"}],            # overlap
])
def test_invalid_hours_are_rejected(client, blocks):
    _, doctor_token, _, _ = _setup(client)
    assert client.put("/api/v1/doctors/me/availability", json={"blocks": blocks}, headers=auth(doctor_token)).status_code == 422


def test_only_doctors_can_manage_hours(client):
    _, _, _, patient = _setup(client)
    assert client.get("/api/v1/doctors/me/availability", headers=auth(patient)).status_code == 404
    assert client.put("/api/v1/doctors/me/availability", json={"blocks": []}, headers=auth(patient)).status_code == 404


# --- Hospital time zone -----------------------------------------------

def test_slots_follow_hospital_time_zone(client):
    hospital_id, _, doctor_id, _ = _setup(client)
    admin = create_super_admin_and_login(client)
    resp = client.patch(f"/api/v1/admin/platform/hospitals/{hospital_id}", json={"timezone": "Europe/London"}, headers=auth(admin))
    assert resp.status_code == 200 and resp.json()["timezone"] == "Europe/London"

    body = _slots(client, doctor_id)
    first = next(d for d in body["days"][1:] if d["slots"])["slots"][0]
    assert body["timezone"] == "Europe/London" and first["label"] == "09:00"
    assert datetime.fromisoformat(first["start"]).astimezone(ZoneInfo("Europe/London")).strftime("%H:%M") == "09:00"

    bad = client.patch(f"/api/v1/admin/platform/hospitals/{hospital_id}", json={"timezone": "Mars/Olympus"}, headers=auth(admin))
    assert bad.status_code == 422
