"""
Phase 8 — Prediction API.

The inference service and Celery are replaced with fakes here (the
real model is tested in ai/tests/). What's tested is the backend's own
job: status transitions, storing results, failure handling, retries,
and who is allowed to see which results.
"""
import io

import pytest

from tests.conftest import register_and_login


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# A valid 1x1 PNG. Hardcoded so the backend's tests don't need Pillow —
# the backend itself never decodes images; that's the inference service's job.
TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def _png_b64() -> str:
    return TINY_PNG_B64


FAKE_RESULT = {
    "predicted_class": "eczema",
    "label": "Signs consistent with eczema",
    "confidence": 0.81,
    "all_probabilities": {"acne": 0.05, "eczema": 0.81, "fungal": 0.09, "normal": 0.05},
    "guidance": "See a dermatologist.",
    "disclaimer": "Not a diagnosis.",
    "model_name": "mobilenetv2-skin-4class",
}


@pytest.fixture()
def fake_inference(monkeypatch):
    """Replaces the HTTP call to the inference service."""
    import app.services.inference_client as inference_client

    calls = []

    def _fake_predict(image_bytes, content_type):
        calls.append(content_type)
        return {**FAKE_RESULT, "gradcam_png_base64": _png_b64()}

    monkeypatch.setattr(inference_client, "predict", _fake_predict)
    return calls


def _run_worker(image_id):
    """Does what the Celery worker would do, against the test database."""
    import uuid

    from app.db.session import get_db
    from app.main import app
    from app.services.prediction_service import run_analysis

    db = next(app.dependency_overrides[get_db]())
    try:
        run_analysis(db, uuid.UUID(image_id))
    finally:
        db.close()


def _patient_with_image(client, email="ai-patient@example.com"):
    token = register_and_login(client, email=email)
    client.post("/api/v1/patients/me", json={}, headers=auth(token))
    resp = client.post(
        "/api/v1/patients/me/images",
        files={"file": ("rash.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg")},
        headers=auth(token),
    )
    return token, resp.json()


def test_upload_queues_analysis(client):
    _, image = _patient_with_image(client)
    assert image["status"] == "queued_for_analysis"
    assert image["prediction"] is None


def test_successful_analysis_stores_prediction_and_heatmap(client, fake_inference, tmp_path):
    token, image = _patient_with_image(client)
    _run_worker(image["id"])

    listed = client.get("/api/v1/patients/me/images", headers=auth(token)).json()[0]
    assert listed["status"] == "analyzed"
    pred = listed["prediction"]
    assert pred["predicted_class"] == "eczema"
    assert pred["confidence"] == pytest.approx(0.81)
    assert set(pred["all_probabilities"]) == {"acne", "eczema", "fungal", "normal"}
    assert pred["disclaimer"]
    # the heatmap was actually written to storage
    heatmap_file = tmp_path / pred["gradcam_url"].removeprefix("/uploads/")
    assert heatmap_file.exists()
    assert fake_inference == ["image/jpeg"]


def test_inference_service_down_marks_failed_with_safe_message(client, monkeypatch):
    import app.services.inference_client as inference_client
    from app.services.inference_client import InferenceServiceError

    def _down(*args):
        raise InferenceServiceError("The analysis service is unavailable right now. Please retry in a minute.")

    monkeypatch.setattr(inference_client, "predict", _down)
    token, image = _patient_with_image(client)
    _run_worker(image["id"])

    listed = client.get("/api/v1/patients/me/images", headers=auth(token)).json()[0]
    assert listed["status"] == "failed"
    assert "unavailable" in listed["analysis_error"]
    assert listed["prediction"] is None


def test_unexpected_error_shows_generic_message_not_internals(client, monkeypatch):
    import app.services.inference_client as inference_client

    def _crash(*args):
        raise RuntimeError("secret internal stack detail")

    monkeypatch.setattr(inference_client, "predict", _crash)
    token, image = _patient_with_image(client)
    _run_worker(image["id"])

    listed = client.get("/api/v1/patients/me/images", headers=auth(token)).json()[0]
    assert listed["status"] == "failed"
    assert "secret" not in listed["analysis_error"]


def test_failed_image_can_be_retried(client, monkeypatch, fake_inference):
    import app.services.inference_client as inference_client
    from app.services.inference_client import InferenceServiceError

    real_fake = inference_client.predict
    monkeypatch.setattr(inference_client, "predict", lambda *a: (_ for _ in ()).throw(InferenceServiceError("down")))
    token, image = _patient_with_image(client)
    _run_worker(image["id"])

    resp = client.post(f"/api/v1/patients/me/images/{image['id']}/analyze", headers=auth(token))
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued_for_analysis"
    assert resp.json()["analysis_error"] is None

    monkeypatch.setattr(inference_client, "predict", real_fake)  # service is back
    _run_worker(image["id"])
    listed = client.get("/api/v1/patients/me/images", headers=auth(token)).json()[0]
    assert listed["status"] == "analyzed"


def test_cannot_reanalyze_while_queued_or_after_success(client, fake_inference):
    token, image = _patient_with_image(client)
    url = f"/api/v1/patients/me/images/{image['id']}/analyze"

    assert client.post(url, headers=auth(token)).status_code == 409  # still queued
    _run_worker(image["id"])
    assert client.post(url, headers=auth(token)).status_code == 409  # already analyzed


def test_patient_cannot_analyze_another_patients_image(client):
    _, image = _patient_with_image(client, email="owner@example.com")
    other_token = register_and_login(client, email="other@example.com")
    client.post("/api/v1/patients/me", json={}, headers=auth(other_token))

    resp = client.post(f"/api/v1/patients/me/images/{image['id']}/analyze", headers=auth(other_token))
    assert resp.status_code == 404


def test_broker_down_marks_image_failed_instead_of_stuck_queued(client, monkeypatch):
    import app.services.prediction_service as prediction_service

    def _broker_down(image_id):
        raise ConnectionError("amqp unreachable")

    monkeypatch.setattr(prediction_service, "enqueue_analysis", _broker_down)
    _, image = _patient_with_image(client)
    assert image["status"] == "failed"
    assert image["analysis_error"]


# --- Doctor access to AI results ---

def _seed_hospital():
    from app.db.session import get_db
    from app.main import app
    from app.schemas.hospital import HospitalCreate
    from app.services.hospital_service import create_hospital

    db = next(app.dependency_overrides[get_db]())
    try:
        return str(create_hospital(db, HospitalCreate(name="AI Clinic", slug="ai-clinic"), created_by_user_id=None).id)
    finally:
        db.close()


def _doctor(client, hospital_id, email, license_no):
    token = register_and_login(client, email=email, hospital_slug="ai-clinic")
    doc = client.post("/api/v1/doctors/me", json={"hospital_id": hospital_id, "license_number": license_no}, headers=auth(token))
    return token, doc.json()["id"]


def test_doctor_with_shared_appointment_sees_patient_ai_results(client, fake_inference):
    hospital_id = _seed_hospital()
    patient_token, image = _patient_with_image(client)
    _run_worker(image["id"])
    doctor_token, doctor_id = _doctor(client, hospital_id, "ai-doc@example.com", "LIC-AI-1")
    client.post("/api/v1/appointments", json={"doctor_id": doctor_id, "scheduled_at": "2027-06-01T10:00:00Z"}, headers=auth(patient_token))
    patient_id = client.get("/api/v1/patients/me", headers=auth(patient_token)).json()["id"]

    resp = client.get(f"/api/v1/doctors/me/patients/{patient_id}/images", headers=auth(doctor_token))
    assert resp.status_code == 200
    assert resp.json()[0]["prediction"]["predicted_class"] == "eczema"


def test_doctor_without_shared_appointment_is_blocked(client):
    hospital_id = _seed_hospital()
    patient_token, _ = _patient_with_image(client)
    doctor_token, _ = _doctor(client, hospital_id, "nosy-doc@example.com", "LIC-AI-2")
    patient_id = client.get("/api/v1/patients/me", headers=auth(patient_token)).json()["id"]

    resp = client.get(f"/api/v1/doctors/me/patients/{patient_id}/images", headers=auth(doctor_token))
    assert resp.status_code == 403
