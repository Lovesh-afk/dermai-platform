"""Integration tests for Phase 6 — Admin Portal. Heavy emphasis on the
RBAC boundaries (SUPER_ADMIN vs HOSPITAL_ADMIN vs regular users), same
approach as Phase 5's doctor-portal tests — proving the walls actually
hold, not just that the happy path works."""
from tests.conftest import create_super_admin_and_login, register_and_login


def _create_hospital(client, super_token, slug, name=None):
    resp = client.post(
        "/api/v1/admin/platform/hospitals",
        json={"name": name or slug.title(), "slug": slug},
        headers={"Authorization": f"Bearer {super_token}"},
    )
    return resp.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Hospital creation (SUPER_ADMIN only) ---

def test_create_hospital_requires_super_admin(client):
    token = register_and_login(client, email="regular@example.com")
    resp = client.post("/api/v1/admin/platform/hospitals", json={"name": "X", "slug": "x-clinic"}, headers=auth_headers(token))
    assert resp.status_code == 403


def test_create_hospital_unauthenticated_rejected(client):
    resp = client.post("/api/v1/admin/platform/hospitals", json={"name": "X", "slug": "x-clinic"})
    assert resp.status_code == 401


def test_super_admin_can_create_hospital(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "new-clinic")
    assert hospital["slug"] == "new-clinic"


def test_duplicate_hospital_slug_returns_409(client):
    super_token = create_super_admin_and_login(client)
    _create_hospital(client, super_token, "dup-clinic")

    resp = client.post(
        "/api/v1/admin/platform/hospitals", json={"name": "Dup 2", "slug": "dup-clinic"}, headers=auth_headers(super_token)
    )
    assert resp.status_code == 409


# --- Platform stats (SUPER_ADMIN only) ---

def test_platform_stats_requires_super_admin(client):
    token = register_and_login(client, email="notadmin@example.com")
    resp = client.get("/api/v1/admin/platform/stats", headers=auth_headers(token))
    assert resp.status_code == 403


def test_platform_stats_counts_correctly(client):
    super_token = create_super_admin_and_login(client)
    _create_hospital(client, super_token, "stats-clinic")
    register_and_login(client, email="stats-patient@example.com", hospital_slug="stats-clinic")

    resp = client.get("/api/v1/admin/platform/stats", headers=auth_headers(super_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_hospitals"] == 1
    assert body["total_users"] >= 2  # super admin + patient


# --- Promoting a hospital admin ---

def test_promote_hospital_admin_full_flow(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "promo2-clinic")
    register_and_login(client, email="future-admin2@example.com", hospital_slug="promo2-clinic")

    resp = client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "future-admin2@example.com"},
        headers=auth_headers(super_token),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "HOSPITAL_ADMIN"


def test_promote_unknown_email_returns_404(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "promo3-clinic")

    resp = client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "doesnotexist@example.com"},
        headers=auth_headers(super_token),
    )
    assert resp.status_code == 404


def test_regular_user_cannot_promote_admins(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "promo4-clinic")
    patient_token = register_and_login(client, email="sneaky@example.com", hospital_slug="promo4-clinic")

    resp = client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "sneaky@example.com"},
        headers=auth_headers(patient_token),
    )
    assert resp.status_code == 403


# --- Hospital-scoped admin (HOSPITAL_ADMIN) ---

def test_hospital_admin_sees_only_their_own_hospital_stats(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "scoped-clinic")
    register_and_login(client, email="scoped-admin@example.com", hospital_slug="scoped-clinic")
    client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "scoped-admin@example.com"},
        headers=auth_headers(super_token),
    )
    admin_token = client.post("/api/v1/auth/login", json={"email": "scoped-admin@example.com", "password": "strongpass123"}).json()["access_token"]

    resp = client.get("/api/v1/admin/hospital/stats", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["hospital_id"] == hospital["id"]


def test_regular_patient_cannot_access_hospital_admin_endpoints(client):
    super_token = create_super_admin_and_login(client)
    _create_hospital(client, super_token, "noaccess-clinic")
    patient_token = register_and_login(client, email="noaccess-patient@example.com", hospital_slug="noaccess-clinic")

    resp = client.get("/api/v1/admin/hospital/stats", headers=auth_headers(patient_token))
    assert resp.status_code == 403


def test_super_admin_using_hospital_scope_without_hospital_returns_400(client):
    """A SUPER_ADMIN account has no hospital_id of its own — hitting
    the hospital-scoped endpoints (meant for HOSPITAL_ADMIN) should
    give a clear error, not a confusing 500 or empty result."""
    super_token = create_super_admin_and_login(client)
    resp = client.get("/api/v1/admin/hospital/stats", headers=auth_headers(super_token))
    assert resp.status_code == 400


def test_hospital_admin_sees_staff_list(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "staff-clinic")
    register_and_login(client, email="staff-admin@example.com", hospital_slug="staff-clinic")
    client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "staff-admin@example.com"},
        headers=auth_headers(super_token),
    )
    admin_token = client.post("/api/v1/auth/login", json={"email": "staff-admin@example.com", "password": "strongpass123"}).json()["access_token"]

    resp = client.get("/api/v1/admin/hospital/staff", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["role"] == "HOSPITAL_ADMIN"


# --- Hospital update (SUPER_ADMIN only) ---

def test_super_admin_can_update_hospital(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "update-clinic")

    resp = client.patch(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}", json={"is_active": False}, headers=auth_headers(super_token)
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_hospital_admin_cannot_update_hospital(client):
    super_token = create_super_admin_and_login(client)
    hospital = _create_hospital(client, super_token, "noupdate-clinic")
    register_and_login(client, email="noupdate-admin@example.com", hospital_slug="noupdate-clinic")
    client.post(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}/admins",
        json={"email": "noupdate-admin@example.com"},
        headers=auth_headers(super_token),
    )
    admin_token = client.post("/api/v1/auth/login", json={"email": "noupdate-admin@example.com", "password": "strongpass123"}).json()["access_token"]

    resp = client.patch(
        f"/api/v1/admin/platform/hospitals/{hospital['id']}", json={"is_active": False}, headers=auth_headers(admin_token)
    )
    assert resp.status_code == 403
