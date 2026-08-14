"""Unit tests for Phase 2: MFA, refresh-token rotation/revocation,
and password reset. Same pattern as test_auth_service.py — service
layer only, no FastAPI/HTTP involved."""
import pyotp
import pytest

from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidMFACodeError,
    InvalidResetTokenError,
)
from app.models.role import Role
from app.schemas.auth import UserLogin, UserRegister
from app.services import auth_service


def _seed_default_role(db_session, hospital_id=None):
    role = Role(name="PATIENT", permissions=["appointments:read"], hospital_id=hospital_id)
    db_session.add(role)
    db_session.commit()
    return role


def _register_and_get_user(db_session, email="mfa@example.com", password="strongpass123"):
    _seed_default_role(db_session)
    payload = UserRegister(email=email, password=password, full_name="MFA User")
    return auth_service.register_user(db_session, payload)


# --- Refresh token rotation & revocation ---

def test_login_without_mfa_returns_full_tokens(db_session):
    _register_and_get_user(db_session)
    result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))

    assert result.mfa_required is False
    assert result.access_token
    assert result.refresh_token


def test_refresh_token_rotates_and_old_one_stops_working(db_session):
    _register_and_get_user(db_session)
    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))
    old_refresh = login_result.refresh_token

    new_tokens = auth_service.refresh_access_token(db_session, old_refresh)
    assert new_tokens.refresh_token != old_refresh

    # Old refresh token must now be dead (rotation)
    with pytest.raises(InvalidCredentialsError):
        auth_service.refresh_access_token(db_session, old_refresh)


def test_logout_revokes_refresh_token(db_session):
    _register_and_get_user(db_session)
    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))

    auth_service.logout(db_session, login_result.refresh_token)

    with pytest.raises(InvalidCredentialsError):
        auth_service.refresh_access_token(db_session, login_result.refresh_token)


def test_logout_is_idempotent_on_unknown_token(db_session):
    # Should not raise even though this token was never issued
    auth_service.logout(db_session, "not-a-real-token")


# --- MFA setup & login ---

def test_mfa_setup_does_not_enable_until_verified(db_session):
    user = _register_and_get_user(db_session)
    secret, uri = auth_service.start_mfa_setup(db_session, user)

    assert secret
    assert "otpauth://totp" in uri
    assert user.is_mfa_enabled is False  # not yet verified


def test_mfa_setup_verify_enables_mfa_and_requires_it_on_login(db_session):
    user = _register_and_get_user(db_session)
    secret, _ = auth_service.start_mfa_setup(db_session, user)

    valid_code = pyotp.TOTP(secret).now()
    auth_service.verify_mfa_setup(db_session, user, valid_code)

    assert user.is_mfa_enabled is True

    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))
    assert login_result.mfa_required is True
    assert login_result.mfa_pending_token
    assert login_result.access_token is None


def test_mfa_verify_setup_wrong_code_raises(db_session):
    user = _register_and_get_user(db_session)
    auth_service.start_mfa_setup(db_session, user)

    with pytest.raises(InvalidMFACodeError):
        auth_service.verify_mfa_setup(db_session, user, "000000")


def test_full_mfa_login_flow(db_session):
    user = _register_and_get_user(db_session)
    secret, _ = auth_service.start_mfa_setup(db_session, user)
    auth_service.verify_mfa_setup(db_session, user, pyotp.TOTP(secret).now())

    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))
    tokens = auth_service.verify_mfa_and_login(db_session, login_result.mfa_pending_token, pyotp.TOTP(secret).now())

    assert tokens.access_token
    assert tokens.refresh_token


def test_mfa_login_verify_wrong_code_raises(db_session):
    user = _register_and_get_user(db_session)
    secret, _ = auth_service.start_mfa_setup(db_session, user)
    auth_service.verify_mfa_setup(db_session, user, pyotp.TOTP(secret).now())

    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))

    with pytest.raises(InvalidMFACodeError):
        auth_service.verify_mfa_and_login(db_session, login_result.mfa_pending_token, "000000")


def test_disable_mfa_requires_correct_password_and_revokes_sessions(db_session):
    user = _register_and_get_user(db_session)
    secret, _ = auth_service.start_mfa_setup(db_session, user)
    auth_service.verify_mfa_setup(db_session, user, pyotp.TOTP(secret).now())

    login_result = auth_service.authenticate_user(db_session, UserLogin(email="mfa@example.com", password="strongpass123"))
    tokens = auth_service.verify_mfa_and_login(db_session, login_result.mfa_pending_token, pyotp.TOTP(secret).now())

    with pytest.raises(InvalidCredentialsError):
        auth_service.disable_mfa(db_session, user, "wrongpassword")

    auth_service.disable_mfa(db_session, user, "strongpass123")
    assert user.is_mfa_enabled is False

    # Sessions issued before disabling MFA should now be revoked
    with pytest.raises(InvalidCredentialsError):
        auth_service.refresh_access_token(db_session, tokens.refresh_token)


# --- Password reset ---

def test_password_reset_request_returns_generic_message_for_unknown_email(db_session):
    result = auth_service.request_password_reset(db_session, "doesnotexist@example.com")
    assert result.dev_reset_token is None
    assert "if an account" in result.message.lower()


def test_password_reset_full_flow(db_session):
    _register_and_get_user(db_session, email="reset@example.com", password="oldpassword123")

    result = auth_service.request_password_reset(db_session, "reset@example.com")
    assert result.dev_reset_token

    auth_service.confirm_password_reset(db_session, result.dev_reset_token, "newpassword456")

    # Old password should no longer work
    with pytest.raises(InvalidCredentialsError):
        auth_service.authenticate_user(db_session, UserLogin(email="reset@example.com", password="oldpassword123"))

    # New password should work
    login_result = auth_service.authenticate_user(db_session, UserLogin(email="reset@example.com", password="newpassword456"))
    assert login_result.mfa_required is False


def test_password_reset_token_is_single_use(db_session):
    _register_and_get_user(db_session, email="reset2@example.com", password="oldpassword123")
    result = auth_service.request_password_reset(db_session, "reset2@example.com")

    auth_service.confirm_password_reset(db_session, result.dev_reset_token, "newpassword456")

    with pytest.raises(InvalidResetTokenError):
        auth_service.confirm_password_reset(db_session, result.dev_reset_token, "anotherpassword789")


def test_password_reset_invalid_token_raises(db_session):
    with pytest.raises(InvalidResetTokenError):
        auth_service.confirm_password_reset(db_session, "not-a-real-token", "newpassword456")
