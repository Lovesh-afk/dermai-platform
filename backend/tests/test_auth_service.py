"""Unit tests for the auth service layer — the whole point of keeping
business logic out of endpoints is that this file doesn't need FastAPI
or a running server."""
import pytest

from app.core.exceptions import AlreadyExistsError, InvalidCredentialsError, NotFoundError
from app.models.hospital import Hospital
from app.models.role import Role
from app.schemas.auth import UserLogin, UserRegister
from app.services import auth_service


def _seed_default_role(db_session, hospital_id=None):
    role = Role(name="PATIENT", permissions=["appointments:read"], hospital_id=hospital_id)
    db_session.add(role)
    db_session.commit()
    return role


def test_register_user_success(db_session):
    _seed_default_role(db_session)
    payload = UserRegister(email="patient@example.com", password="strongpass123", full_name="Jane Doe")

    user = auth_service.register_user(db_session, payload)

    assert user.email == "patient@example.com"
    assert user.hashed_password != "strongpass123"  # must be hashed, not plaintext


def test_register_duplicate_email_raises(db_session):
    _seed_default_role(db_session)
    payload = UserRegister(email="dup@example.com", password="strongpass123", full_name="Jane Doe")
    auth_service.register_user(db_session, payload)

    with pytest.raises(AlreadyExistsError):
        auth_service.register_user(db_session, payload)


def test_register_unknown_hospital_slug_raises(db_session):
    payload = UserRegister(email="x@example.com", password="strongpass123", full_name="X", hospital_slug="does-not-exist")

    with pytest.raises(NotFoundError):
        auth_service.register_user(db_session, payload)


def test_authenticate_wrong_password_raises(db_session):
    _seed_default_role(db_session)
    payload = UserRegister(email="p2@example.com", password="strongpass123", full_name="P Two")
    auth_service.register_user(db_session, payload)

    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate_user(db_session, UserLogin(email="p2@example.com", password="wrongpass"))


def test_authenticate_and_issue_tokens_success(db_session):
    _seed_default_role(db_session)
    payload = UserRegister(email="p3@example.com", password="strongpass123", full_name="P Three")
    auth_service.register_user(db_session, payload)

    user = auth_service.authenticate_user(db_session, UserLogin(email="p3@example.com", password="strongpass123"))
    tokens = auth_service.issue_tokens(db_session, user)

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


def test_refresh_access_token_with_invalid_token_raises(db_session):
    with pytest.raises(InvalidCredentialsError):
        auth_service.refresh_access_token(db_session, "not-a-real-token")
