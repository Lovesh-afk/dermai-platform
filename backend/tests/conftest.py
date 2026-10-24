"""
Test fixtures. Uses a separate in-memory-style SQLite DB for speed in
unit tests of services; integration tests against the real Postgres
schema belong in a docker-compose based CI job (Phase 15), not here.
"""
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient wired to its own isolated in-memory DB
    (shared across requests within one test via StaticPool, since
    :memory: SQLite is otherwise per-connection). Local file uploads
    are redirected to a pytest tmp_path so tests never touch the
    real backend/uploads directory."""
    import app.services.storage_service as storage_service

    monkeypatch.setattr(storage_service, "LOCAL_UPLOAD_DIR", tmp_path)

    # No message broker in tests: record queued image IDs instead of
    # sending them to Celery. Tests run the analysis explicitly.
    import app.services.prediction_service as prediction_service

    queued_ids = []
    monkeypatch.setattr(prediction_service, "enqueue_analysis", lambda image_id: queued_ids.append(image_id))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_and_login(client, email="patient@example.com", password="strongpass123", full_name="Test Patient", hospital_slug=None):
    """Helper: registers a user (seeding a PATIENT role first if
    needed), logs in, and returns the access token."""
    from sqlalchemy import select

    from app.db.session import get_db
    from app.main import app
    from app.models.role import Role

    override = app.dependency_overrides[get_db]
    db = next(override())
    try:
        existing = db.execute(select(Role).where(Role.name == "PATIENT", Role.hospital_id.is_(None))).scalar_one_or_none()
        if not existing:
            db.add(Role(name="PATIENT", permissions=["appointments:read", "appointments:write"], hospital_id=None))
            db.commit()
    finally:
        db.close()

    client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": full_name, "hospital_slug": hospital_slug})
    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_resp.json()["access_token"]


def create_super_admin_and_login(client, email="super@example.com", password="strongpass123"):
    """Bootstraps a SUPER_ADMIN account directly in the test DB —
    mirrors what scripts/seed_roles.py does for real deployments, since
    there's no API endpoint that can create the very first admin (you'd
    need to already be one to call any admin endpoint)."""
    from app.core.security import hash_password
    from app.db.session import get_db
    from app.main import app
    from app.models.role import Role
    from app.models.user import User

    override = app.dependency_overrides[get_db]
    db = next(override())
    try:
        role = Role(name="SUPER_ADMIN", permissions=["*"], hospital_id=None)
        db.add(role)
        db.commit()
        db.refresh(role)

        user = User(email=email, hashed_password=hash_password(password), full_name="Super Admin", role_id=role.id, hospital_id=None)
        db.add(user)
        db.commit()
    finally:
        db.close()

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_resp.json()["access_token"]


def slot_at(days_ahead: int = 1, index: int = 0):
    """A guaranteed-bookable appointment time under the default hours
    (Mon-Fri 09:00-17:00, Asia/Kolkata): the first weekday at least
    `days_ahead` days from now, at 09:00 + index x 30 min (index 0-15).
    Returned as a UTC datetime, like the API stores it."""
    from datetime import datetime, time, timedelta, timezone
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("Asia/Kolkata")
    day = datetime.now(zone).date() + timedelta(days=days_ahead)
    while day.weekday() >= 5:  # skip Saturday/Sunday
        day += timedelta(days=1)
    local = datetime.combine(day, time(9, 0), tzinfo=zone) + timedelta(minutes=30 * index)
    return local.astimezone(timezone.utc)
