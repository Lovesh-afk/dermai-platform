"""Tests for the public hospital directory (read-only, no auth) and
confirms hospital creation is genuinely locked to SUPER_ADMIN now —
see test_admin_api.py for the actual creation-flow tests."""
from tests.conftest import create_super_admin_and_login, register_and_login


def _create_hospital(client, slug, name=None):
    token = create_super_admin_and_login(client, email=f"super-{slug}@example.com")
    resp = client.post(
        "/api/v1/admin/platform/hospitals",
        json={"name": name or slug.title(), "slug": slug},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp


def test_post_to_public_hospitals_endpoint_no_longer_exists(client):
    """The old open, unauthenticated hospital-creation endpoint from
    Phase 4/5 must be gone — creation moved to /admin/platform/hospitals."""
    resp = client.post("/api/v1/hospitals", json={"name": "Should Not Work", "slug": "should-not-work"})
    assert resp.status_code in (404, 405)


def test_list_hospitals_is_public(client):
    _create_hospital(client, "a-clinic")
    resp = client.get("/api/v1/hospitals")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_hospital_by_id_is_public(client):
    create_resp = _create_hospital(client, "lookup-clinic")
    hospital_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/hospitals/{hospital_id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "lookup-clinic"


def test_get_unknown_hospital_returns_404(client):
    resp = client.get("/api/v1/hospitals/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_newly_created_hospital_is_immediately_usable_for_registration(client):
    """The real point of hospital creation: it must be joinable right
    away, not require a separate manual role-seeding step."""
    create_resp = _create_hospital(client, "fresh-clinic")
    assert create_resp.status_code == 201

    register_resp = client.post(
        "/api/v1/auth/register",
        json={"email": "newpatient@example.com", "password": "strongpass123", "full_name": "New Patient", "hospital_slug": "fresh-clinic"},
    )
    assert register_resp.status_code == 201
    assert register_resp.json()["hospital_id"] is not None
