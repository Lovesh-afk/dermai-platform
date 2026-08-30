"""Tests for the (deliberately open, temporary) hospital creation
endpoint — see hospital_service.py's docstring for why this has no
auth yet. Also verifies the side effect that matters most: a newly
created hospital is immediately usable for registration, since it
seeds a PATIENT role for it."""
from tests.conftest import register_and_login


def test_create_hospital_success(client):
    resp = client.post("/api/v1/hospitals", json={"name": "Sunrise Clinic", "slug": "sunrise-clinic"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "sunrise-clinic"
    assert body["is_active"] is True


def test_create_hospital_duplicate_slug_raises_409(client):
    client.post("/api/v1/hospitals", json={"name": "Sunrise Clinic", "slug": "sunrise-clinic"})
    resp = client.post("/api/v1/hospitals", json={"name": "Another Name", "slug": "sunrise-clinic"})
    assert resp.status_code == 409


def test_create_hospital_rejects_invalid_slug(client):
    resp = client.post("/api/v1/hospitals", json={"name": "Bad Slug Clinic", "slug": "Not A Valid Slug!"})
    assert resp.status_code == 422


def test_list_hospitals(client):
    client.post("/api/v1/hospitals", json={"name": "A Clinic", "slug": "a-clinic"})
    client.post("/api/v1/hospitals", json={"name": "B Clinic", "slug": "b-clinic"})

    resp = client.get("/api/v1/hospitals")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_newly_created_hospital_is_immediately_usable_for_registration(client):
    """The real point of this endpoint: a hospital created via the API
    must be joinable right away, not require a separate manual role
    seeding step — that's the bug this test guards against."""
    create_resp = client.post("/api/v1/hospitals", json={"name": "Fresh Clinic", "slug": "fresh-clinic"})
    assert create_resp.status_code == 201

    register_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "newpatient@example.com", "password": "strongpass123", "full_name": "New Patient", "hospital_slug": "fresh-clinic"},
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["hospital_id"] is not None


def test_get_hospital_by_id(client):
    create_resp = client.post("/api/v1/hospitals", json={"name": "Lookup Clinic", "slug": "lookup-clinic"})
    hospital_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/hospitals/{hospital_id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "lookup-clinic"


def test_get_unknown_hospital_returns_404(client):
    resp = client.get("/api/v1/hospitals/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
