"""Integration tests for Phase 5 — Doctor Portal endpoints. Focused
heavily on the RBAC boundaries (a doctor can only see/act on their
own queue and their own patients) since that's the part most likely
to have a subtle bug and least likely to be caught by "does it run"
manual testing."""
import pytest

from tests.conftest import register_and_login, slot_at


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_hospital(client):
    """Seeds a hospital directly via the service layer (not a bare
    ORM insert) so it gets its PATIENT/DOCTOR/HOSPITAL_ADMIN roles the
    same way a real hospital created through the app would — a bare
    Hospital() row with no roles let registration silently fall back
    to the wrong role scope, a bug only exposed once the
    register_and_login test helper started actually passing
    hospital_slug through (see conftest.py)."""
    from app.db.session import get_db
    from app.main import app
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = next(app.dependency_overrides[get_db]())
    hospital = create_hospital(db, HospitalCreate(name="City Derma Clinic", slug="city-derma"), created_by_user_id=None)
    hospital_id = str(hospital.id)
    db.close()
    return hospital_id


def _setup_patient_and_doctor(client, hospital_id, patient_email="rbac-patient@example.com", doctor_email="rbac-doctor@example.com", license_no="LIC-RBAC-1"):
    patient_token = register_and_login(client, email=patient_email)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(patient_token))

    doctor_token = register_and_login(client, email=doctor_email, hospital_slug="city-derma")
    doc_resp = client.post(
        "/api/v1/doctors/me",
        json={"hospital_id": hospital_id, "license_number": license_no},
        headers=auth_headers(doctor_token),
    )
    doctor_id = doc_resp.json()["id"]

    return patient_token, doctor_token, doctor_id


def test_get_my_doctor_profile_requires_profile_first(client):
    hospital_id = _seed_hospital(client)
    doctor_token = register_and_login(client, email="nodoc@example.com", hospital_slug="city-derma")

    resp = client.get("/api/v1/doctors/me", headers=auth_headers(doctor_token))
    assert resp.status_code == 404


def test_update_my_doctor_profile(client):
    hospital_id = _seed_hospital(client)
    _, doctor_token, _ = _setup_patient_and_doctor(client, hospital_id)

    resp = client.patch("/api/v1/doctors/me", json={"is_accepting_appointments": False, "bio": "On leave"}, headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    assert resp.json()["is_accepting_appointments"] is False
    assert resp.json()["bio"] == "On leave"


def test_doctor_sees_booked_appointment_in_queue(client):
    hospital_id = _seed_hospital(client)
    patient_token, doctor_token, doctor_id = _setup_patient_and_doctor(client, hospital_id)

    client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": slot_at(index=0).isoformat()},
        headers=auth_headers(patient_token),
    )

    resp = client.get("/api/v1/doctors/me/appointments", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_doctor_can_confirm_and_complete_appointment(client):
    hospital_id = _seed_hospital(client)
    patient_token, doctor_token, doctor_id = _setup_patient_and_doctor(client, hospital_id)

    book_resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": slot_at(index=1).isoformat()},
        headers=auth_headers(patient_token),
    )
    appointment_id = book_resp.json()["id"]

    confirm_resp = client.patch(
        f"/api/v1/appointments/{appointment_id}/status", json={"status": "confirmed"}, headers=auth_headers(doctor_token)
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"

    complete_resp = client.patch(
        f"/api/v1/appointments/{appointment_id}/status", json={"status": "completed"}, headers=auth_headers(doctor_token)
    )
    assert complete_resp.json()["status"] == "completed"


def test_patient_cannot_update_appointment_status(client):
    """Status transitions are a doctor-only action — a patient hitting
    this endpoint should be rejected, not silently succeed."""
    hospital_id = _seed_hospital(client)
    patient_token, doctor_token, doctor_id = _setup_patient_and_doctor(client, hospital_id)

    book_resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": slot_at(index=2).isoformat()},
        headers=auth_headers(patient_token),
    )
    appointment_id = book_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/appointments/{appointment_id}/status", json={"status": "confirmed"}, headers=auth_headers(patient_token)
    )
    assert resp.status_code == 403


def test_doctor_cannot_update_another_doctors_appointment(client):
    """The core RBAC boundary of this phase: Doctor B must not be able
    to touch Doctor A's appointment just by guessing/knowing its ID."""
    hospital_id = _seed_hospital(client)
    patient_token, doctor_a_token, doctor_a_id = _setup_patient_and_doctor(
        client, hospital_id, patient_email="p1@example.com", doctor_email="doctor-a@example.com", license_no="LIC-A"
    )

    # A second, unrelated doctor
    doctor_b_token = register_and_login(client, email="doctor-b@example.com", hospital_slug="city-derma")
    client.post(
        "/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": "LIC-B"}, headers=auth_headers(doctor_b_token)
    )

    book_resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_a_id, "scheduled_at": slot_at(index=3).isoformat()},
        headers=auth_headers(patient_token),
    )
    appointment_id = book_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/appointments/{appointment_id}/status", json={"status": "confirmed"}, headers=auth_headers(doctor_b_token)
    )
    assert resp.status_code == 403


def test_doctor_sees_patient_after_shared_appointment(client):
    hospital_id = _seed_hospital(client)
    patient_token, doctor_token, doctor_id = _setup_patient_and_doctor(client, hospital_id)

    client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": slot_at(index=4).isoformat()},
        headers=auth_headers(patient_token),
    )

    resp = client.get("/api/v1/doctors/me/patients", headers=auth_headers(doctor_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_doctor_cannot_see_unrelated_patient(client):
    """Second half of the core RBAC boundary: a doctor with zero
    shared appointment history with a patient must be blocked from
    viewing that patient's profile, even by direct ID."""
    hospital_id = _seed_hospital(client)

    # Patient with NO appointment with anyone
    patient_token = register_and_login(client, email="lonely-patient@example.com")
    patient_profile_resp = client.post("/api/v1/patients/me", json={}, headers=auth_headers(patient_token))
    patient_id = patient_profile_resp.json()["id"]

    doctor_token = register_and_login(client, email="curious-doctor@example.com", hospital_slug="city-derma")
    client.post(
        "/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": "LIC-CURIOUS"}, headers=auth_headers(doctor_token)
    )

    resp = client.get(f"/api/v1/doctors/me/patients/{patient_id}", headers=auth_headers(doctor_token))
    assert resp.status_code == 403


def test_doctor_can_create_medical_record_for_shared_patient(client):
    hospital_id = _seed_hospital(client)
    patient_token, doctor_token, doctor_id = _setup_patient_and_doctor(client, hospital_id)

    client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": slot_at(index=5).isoformat()},
        headers=auth_headers(patient_token),
    )
    patient_profile = client.get("/api/v1/patients/me", headers=auth_headers(patient_token)).json()

    resp = client.post(
        "/api/v1/medical-records",
        json={"patient_id": patient_profile["id"], "diagnosis": "Contact dermatitis", "notes": "Avoid the irritant"},
        headers=auth_headers(doctor_token),
    )
    assert resp.status_code == 201
    assert resp.json()["diagnosis"] == "Contact dermatitis"

    # It shows up in the patient's own medical history too
    records = client.get("/api/v1/patients/me/medical-records", headers=auth_headers(patient_token))
    assert len(records.json()) == 1

    # And in the doctor's own created-records list
    doctor_records = client.get("/api/v1/doctors/me/medical-records", headers=auth_headers(doctor_token))
    assert len(doctor_records.json()) == 1


def test_doctor_cannot_create_medical_record_for_unrelated_patient(client):
    hospital_id = _seed_hospital(client)

    patient_token = register_and_login(client, email="unrelated-patient@example.com")
    patient_profile = client.post("/api/v1/patients/me", json={}, headers=auth_headers(patient_token)).json()

    doctor_token = register_and_login(client, email="unrelated-doctor@example.com", hospital_slug="city-derma")
    client.post(
        "/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": "LIC-UNREL"}, headers=auth_headers(doctor_token)
    )

    resp = client.post(
        "/api/v1/medical-records",
        json={"patient_id": patient_profile["id"], "diagnosis": "Should be blocked"},
        headers=auth_headers(doctor_token),
    )
    assert resp.status_code == 403


def test_non_doctor_cannot_create_medical_record(client):
    token = register_and_login(client, email="justapatient@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    resp = client.post(
        "/api/v1/medical-records",
        json={"patient_id": "00000000-0000-0000-0000-000000000000", "diagnosis": "N/A"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
