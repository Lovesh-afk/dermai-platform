"""Phase 10 — doctor recommendations: ranking, reasons, filters, scoping."""
from datetime import datetime, timedelta, timezone

from tests.conftest import register_and_login, slot_at


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


def _doctor(client, hospital_slug, hospital_id, email, name, is_accepting_appointments=True, **profile):
    token = register_and_login(client, email=email, full_name=name, hospital_slug=hospital_slug)
    body = {"hospital_id": hospital_id, "license_number": f"LIC-{email}", **profile}
    resp = client.post("/api/v1/doctors/me", json=body, headers=auth(token))
    assert resp.status_code == 201, resp.text
    if not is_accepting_appointments:  # only settable after creation, as in the real doctor portal
        client.patch("/api/v1/doctors/me", json={"is_accepting_appointments": False}, headers=auth(token))
    return resp.json()["id"]


def _patient(client, email="rec-patient@example.com", hospital_slug=None):
    token = register_and_login(client, email=email, hospital_slug=hospital_slug)
    client.post("/api/v1/patients/me", json={}, headers=auth(token))
    return token


def _recommend(client, token, **params):
    return client.get("/api/v1/patients/me/recommended-doctors", params=params, headers=auth(token))


def _add_photo_prediction(client, token, predicted_class):
    """Stores an analysed photo directly, as if the AI had run."""
    from app.models.prediction import Prediction
    from app.models.skin_image import SkinImage, SkinImageStatus

    patient_id = client.get("/api/v1/patients/me", headers=auth(token)).json()["id"]
    db = _db()
    try:
        import uuid

        image = SkinImage(patient_id=uuid.UUID(patient_id), storage_key="k", file_url="/uploads/k.jpg",
                          content_type="image/jpeg", status=SkinImageStatus.ANALYZED)
        db.add(image)
        db.flush()
        db.add(Prediction(skin_image_id=image.id, predicted_class=predicted_class, label="x", confidence=0.9,
                          all_probabilities={}, guidance="g", disclaimer="d", gradcam_storage_key="h",
                          gradcam_url="/uploads/h.png", model_name="m"))
        db.commit()
    finally:
        db.close()


def test_condition_match_ranks_specialist_first(client):
    hid = _hospital("rec-clinic")
    _doctor(client, "rec-clinic", hid, "general@example.com", "Dr General", years_experience=15)
    _doctor(client, "rec-clinic", hid, "fungal@example.com", "Dr Fungal", years_experience=5,
            bio="Special interest in fungal infections and tinea.")
    token = _patient(client)

    body = _recommend(client, token, condition="fungal").json()
    assert body["condition"] == "fungal" and body["condition_source"] == "selected"
    top = body["doctors"][0]
    assert top["doctor"]["full_name"] == "Dr Fungal"
    assert "Experienced with fungal infections" in top["reasons"]


def test_uses_latest_photo_analysis_when_no_condition_given(client):
    hid = _hospital("photo-clinic")
    _doctor(client, "photo-clinic", hid, "ecz@example.com", "Dr Eczema", bio="Eczema and atopic dermatitis clinic.")
    token = _patient(client)
    _add_photo_prediction(client, token, "eczema")

    body = _recommend(client, token).json()
    assert body["condition"] == "eczema" and body["condition_source"] == "photo"
    assert "Experienced with eczema" in body["doctors"][0]["reasons"]


def test_patient_can_ignore_photo_condition(client):
    """Choosing "Any" in the UI must override the photo-based condition."""
    hid = _hospital("ignore-clinic")
    _doctor(client, "ignore-clinic", hid, "i@example.com", "Dr I")
    token = _patient(client)
    _add_photo_prediction(client, token, "fungal")

    body = _recommend(client, token, use_photo="false").json()
    assert body["condition"] is None and body["condition_source"] is None


def test_normal_photo_result_means_no_condition(client):
    hid = _hospital("normal-clinic")
    _doctor(client, "normal-clinic", hid, "n@example.com", "Dr N")
    token = _patient(client)
    _add_photo_prediction(client, token, "normal")

    body = _recommend(client, token).json()
    assert body["condition"] is None and body["condition_source"] is None
    assert len(body["doctors"]) == 1


def test_doctor_not_accepting_appointments_is_excluded(client):
    hid = _hospital("closed-clinic")
    _doctor(client, "closed-clinic", hid, "open@example.com", "Dr Open")
    _doctor(client, "closed-clinic", hid, "closed@example.com", "Dr Closed", is_accepting_appointments=False)
    token = _patient(client)

    names = [d["doctor"]["full_name"] for d in _recommend(client, token).json()["doctors"]]
    assert names == ["Dr Open"]


def test_busy_doctor_ranks_below_available_one(client):
    hid = _hospital("busy-clinic")
    busy_id = _doctor(client, "busy-clinic", hid, "busy@example.com", "Dr Busy", years_experience=10)
    _doctor(client, "busy-clinic", hid, "free@example.com", "Dr Free", years_experience=10)
    for i in range(5):  # five other patients fill Dr Busy's next two weeks
        t = _patient(client, email=f"filler{i}@example.com")
        when = slot_at(days_ahead=1, index=i).isoformat()
        assert client.post("/api/v1/appointments", json={"doctor_id": busy_id, "scheduled_at": when}, headers=auth(t)).status_code == 201

    token = _patient(client)
    doctors = _recommend(client, token).json()["doctors"]
    assert [d["doctor"]["full_name"] for d in doctors] == ["Dr Free", "Dr Busy"]
    assert "Fully available in the next 2 weeks" in doctors[0]["reasons"]


def test_previous_doctor_gets_continuity_boost(client):
    hid = _hospital("cont-clinic")
    seen_id = _doctor(client, "cont-clinic", hid, "seen@example.com", "Dr Seen")
    _doctor(client, "cont-clinic", hid, "new@example.com", "Dr New")
    token = _patient(client)
    past = slot_at(days_ahead=30).isoformat()  # outside the 2-week busy window
    client.post("/api/v1/appointments", json={"doctor_id": seen_id, "scheduled_at": past}, headers=auth(token))

    top = _recommend(client, token).json()["doctors"][0]
    assert top["doctor"]["full_name"] == "Dr Seen"
    assert "You've booked with this doctor before" in top["reasons"]


def test_max_fee_filter(client):
    hid = _hospital("fee-clinic")
    _doctor(client, "fee-clinic", hid, "cheap@example.com", "Dr Cheap", consultation_fee=500)
    _doctor(client, "fee-clinic", hid, "pricey@example.com", "Dr Pricey", consultation_fee=3000)
    token = _patient(client)

    names = [d["doctor"]["full_name"] for d in _recommend(client, token, max_fee=1000).json()["doctors"]]
    assert names == ["Dr Cheap"]


def test_hospital_patients_only_see_their_hospital(client):
    a, b = _hospital("hosp-a"), _hospital("hosp-b")
    _doctor(client, "hosp-a", a, "da@example.com", "Dr A")
    _doctor(client, "hosp-b", b, "db@example.com", "Dr B")

    hospital_patient = _patient(client, email="in-a@example.com", hospital_slug="hosp-a")
    names = {d["doctor"]["full_name"] for d in _recommend(client, hospital_patient).json()["doctors"]}
    assert names == {"Dr A"}

    independent = _patient(client, email="indie@example.com")  # signed up without a hospital
    names = {d["doctor"]["full_name"] for d in _recommend(client, independent).json()["doctors"]}
    assert names == {"Dr A", "Dr B"}


def test_scores_reasons_and_limit(client):
    hid = _hospital("limit-clinic")
    for i in range(4):
        _doctor(client, "limit-clinic", hid, f"d{i}@example.com", f"Dr {i}", years_experience=i + 1)
    token = _patient(client)

    doctors = _recommend(client, token, limit=2).json()["doctors"]
    assert len(doctors) == 2
    for d in doctors:
        assert 0 <= d["score"] <= 100 and d["reasons"] and d["hospital_name"]


def test_invalid_condition_and_missing_profile(client):
    token = _patient(client)
    assert _recommend(client, token, condition="cancer").status_code == 422

    no_profile = register_and_login(client, email="noprofile@example.com")
    assert _recommend(client, no_profile).status_code == 404


def test_doctor_listing_now_includes_names(client):
    hid = _hospital("names-clinic")
    _doctor(client, "names-clinic", hid, "named@example.com", "Dr Named")
    listing = client.get("/api/v1/doctors", params={"hospital_id": hid}).json()
    assert listing[0]["full_name"] == "Dr Named"
