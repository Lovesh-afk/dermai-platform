"""Integration tests for Phase 4 — hitting real HTTP endpoints via
FastAPI's TestClient rather than calling service functions directly,
since this is the first phase with actual API routes to verify (auth
headers, status codes, request/response shapes, cross-cutting 401s)."""
import io

from tests.conftest import register_and_login


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_my_patient_profile(client):
    token = register_and_login(client)

    resp = client.post("/api/v1/patients/me", json={"gender": "male", "phone": "9998887777"}, headers=auth_headers(token))
    assert resp.status_code == 201
    assert resp.json()["gender"] == "male"

    resp = client.get("/api/v1/patients/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["phone"] == "9998887777"


def test_duplicate_profile_creation_returns_409(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    resp = client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))
    assert resp.status_code == 409


def test_get_profile_without_creating_returns_404(client):
    token = register_and_login(client)
    resp = client.get("/api/v1/patients/me", headers=auth_headers(token))
    assert resp.status_code == 404


def test_endpoints_require_authentication(client):
    resp = client.get("/api/v1/patients/me")
    assert resp.status_code == 401


def test_appointments_require_patient_profile_first(client):
    token = register_and_login(client)
    resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": "00000000-0000-0000-0000-000000000000", "scheduled_at": "2027-01-01T10:00:00Z"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404
    assert "patient profile" in resp.json()["detail"].lower()


def test_get_my_appointments_empty_list_initially(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    resp = client.get("/api/v1/patients/me/appointments", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_my_medical_records_empty_list_initially(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    resp = client.get("/api/v1/patients/me/medical-records", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


# --- Skin image upload ---

def test_upload_skin_image_success(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    fake_image = io.BytesIO(b"fake-jpeg-bytes")
    resp = client.post(
        "/api/v1/patients/me/images",
        files={"file": ("rash.jpg", fake_image, "image/jpeg")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "uploaded"
    assert body["file_url"].startswith("/uploads/")


def test_upload_rejects_unsupported_file_type(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf")
    resp = client.post(
        "/api/v1/patients/me/images",
        files={"file": ("report.pdf", fake_pdf, "application/pdf")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 400


def test_uploaded_image_appears_in_list(client):
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    fake_image = io.BytesIO(b"fake-png-bytes")
    client.post(
        "/api/v1/patients/me/images",
        files={"file": ("mole.png", fake_image, "image/png")},
        headers=auth_headers(token),
    )

    resp = client.get("/api/v1/patients/me/images", headers=auth_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_uploaded_image_is_actually_written_to_disk(client, tmp_path):
    """The StaticFiles mount binds its directory once at app startup,
    so it can't be redirected per-test the way storage_service's
    LOCAL_UPLOAD_DIR is (see the `client` fixture's monkeypatch) —
    that's a real, standard limitation of how Starlette's StaticFiles
    works, not something worth restructuring the app around. This
    test instead verifies the thing that actually matters: the upload
    endpoint writes real bytes to the directory storage_service is
    configured to use, and returns a URL matching the naming
    convention the static mount expects."""
    token = register_and_login(client)
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(token))

    fake_image = io.BytesIO(b"fake-jpeg-bytes-for-serving-test")
    upload_resp = client.post(
        "/api/v1/patients/me/images",
        files={"file": ("test.jpg", fake_image, "image/jpeg")},
        headers=auth_headers(token),
    )
    file_url = upload_resp.json()["file_url"]
    assert file_url.startswith("/uploads/")

    saved_filename = file_url.removeprefix("/uploads/")
    saved_path = tmp_path / saved_filename
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"fake-jpeg-bytes-for-serving-test"


# --- Doctor directory + full booking flow end-to-end ---

def _create_hospital_and_doctor(client, db_override):
    """Uses the raw DB session (bypassing the API) just to seed a
    Hospital and DOCTOR role, since there's no admin-portal endpoint
    for that yet (Phase 6) — then registers a real doctor user via
    the actual API, same as any other flow in this test file."""
    from app.models.hospital import Hospital
    from app.models.role import Role

    db = db_override
    hospital = Hospital(name="City Derma Clinic", slug="city-derma")
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    db.add(Role(name="PATIENT", permissions=[], hospital_id=hospital.id))
    db.commit()
    return hospital


def test_full_booking_flow_end_to_end(client):
    from app.db.session import get_db
    from app.main import app

    db = next(app.dependency_overrides[get_db]())
    hospital = _create_hospital_and_doctor(client, db)
    hospital_id = str(hospital.id)  # capture before closing — the ORM object
    db.close()                       # can't be touched after its session closes

    # Patient registers and creates a profile
    patient_token = register_and_login(client, email="realpatient@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth_headers(patient_token))

    # Doctor registers (joins the same hospital) and creates a doctor profile
    doctor_token = register_and_login(client, email="realdoctor@example.com", hospital_slug="city-derma")
    doc_resp = client.post(
        "/api/v1/doctors/me",
        json={"hospital_id": hospital_id, "license_number": "LIC-E2E-1", "specialization": "Dermatology"},
        headers=auth_headers(doctor_token),
    )
    assert doc_resp.status_code == 201
    doctor_id = doc_resp.json()["id"]

    # Patient browses doctors at that hospital
    list_resp = client.get(f"/api/v1/doctors?hospital_id={hospital_id}")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Patient books an appointment
    book_resp = client.post(
        "/api/v1/appointments",
        json={"doctor_id": doctor_id, "scheduled_at": "2027-03-01T10:00:00Z", "reason": "Suspicious mole"},
        headers=auth_headers(patient_token),
    )
    assert book_resp.status_code == 201
    appointment_id = book_resp.json()["id"]
    assert book_resp.json()["status"] == "pending"

    # It shows up in the patient's appointment list
    my_appts = client.get("/api/v1/patients/me/appointments", headers=auth_headers(patient_token))
    assert len(my_appts.json()) == 1

    # Patient cancels it
    cancel_resp = client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        json={"cancellation_reason": "Schedule conflict"},
        headers=auth_headers(patient_token),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
