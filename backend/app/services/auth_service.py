"""
All auth business logic lives here, not in the endpoint. This is the
unit-test surface — endpoints stay thin and are covered by integration
tests instead.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AlreadyExistsError,
    InvalidCredentialsError,
    InvalidMFACodeError,
    InvalidResetTokenError,
    MFARequiredError,
    NotFoundError,
)
from app.core.security import (
    create_access_token,
    create_mfa_pending_token,
    decode_jwt,
    generate_raw_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.hospital import Hospital
from app.models.password_reset_token import PasswordResetToken
from app.models.role import Role
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import (
    LoginResponse,
    PasswordResetRequestOut,
    TokenPair,
    UserLogin,
    UserRegister,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """SQLite (used in unit tests) doesn't preserve timezone info even
    on a DateTime(timezone=True) column, so a value round-tripped
    through it comes back naive while Postgres would keep it aware.
    Normalize to UTC-aware before comparing so the same service code
    works correctly against both backends."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_user(db: Session, payload: UserRegister) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise AlreadyExistsError(f"A user with email {payload.email} already exists")

    hospital_id = None
    if payload.hospital_slug:
        hospital = db.execute(select(Hospital).where(Hospital.slug == payload.hospital_slug)).scalar_one_or_none()
        if not hospital:
            raise NotFoundError(f"No hospital found with slug {payload.hospital_slug}")
        hospital_id = hospital.id

    role_name = "PATIENT"
    role = db.execute(
        select(Role).where(Role.name == role_name, Role.hospital_id == hospital_id)
    ).scalar_one_or_none()
    if not role:
        raise NotFoundError(f"Default role '{role_name}' is not seeded for this hospital yet")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=role.id,
        hospital_id=hospital_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login / tokens / sessions
# ---------------------------------------------------------------------------

def _issue_token_pair(db: Session, user: User, user_agent: str | None = None) -> TokenPair:
    role = db.get(Role, user.role_id)
    access = create_access_token(
        subject=str(user.id), role=role.name, hospital_id=str(user.hospital_id) if user.hospital_id else None
    )

    raw_refresh = generate_raw_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()

    return TokenPair(access_token=access, refresh_token=raw_refresh)


def authenticate_user(db: Session, payload: UserLogin, user_agent: str | None = None) -> LoginResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password")
    if not user.is_active:
        raise InvalidCredentialsError("This account has been deactivated")

    if user.is_mfa_enabled:
        pending_token = create_mfa_pending_token(subject=str(user.id))
        return LoginResponse(mfa_required=True, mfa_pending_token=pending_token)

    tokens = _issue_token_pair(db, user, user_agent)
    return LoginResponse(mfa_required=False, access_token=tokens.access_token, refresh_token=tokens.refresh_token)


def verify_mfa_and_login(db: Session, mfa_pending_token: str, code: str, user_agent: str | None = None) -> TokenPair:
    payload = decode_jwt(mfa_pending_token)
    if not payload or payload.get("type") != "mfa_pending":
        raise InvalidCredentialsError("Invalid or expired MFA session — please log in again")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active or not user.is_mfa_enabled or not user.mfa_secret:
        raise InvalidCredentialsError("Invalid or expired MFA session — please log in again")

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise InvalidMFACodeError("Incorrect authentication code")

    return _issue_token_pair(db, user, user_agent)


def refresh_access_token(db: Session, raw_refresh_token: str) -> TokenPair:
    """Refresh-token rotation: every use invalidates the old token and
    issues a new one. This limits how long a stolen-but-unused refresh
    token stays useful, and a reused/revoked token failing here is a
    signal worth logging as suspicious in a later phase."""
    token_hash = hash_token(raw_refresh_token)
    session = db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash)).scalar_one_or_none()

    if not session or session.revoked or _aware(session.expires_at) < _utcnow():
        raise InvalidCredentialsError("Invalid or expired refresh token")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    session.revoked = True  # rotate: this token is now spent
    db.add(session)
    db.commit()

    return _issue_token_pair(db, user)


def logout(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    session = db.execute(select(UserSession).where(UserSession.refresh_token_hash == token_hash)).scalar_one_or_none()
    if session and not session.revoked:
        session.revoked = True
        db.add(session)
        db.commit()
    # Intentionally silent if the token doesn't exist/is already revoked —
    # logout is idempotent from the caller's point of view.


def revoke_all_sessions(db: Session, user_id) -> int:
    """Used by 'log out of all devices' and by MFA-disable/password-change
    flows that should invalidate any tokens issued before the change."""
    sessions = db.execute(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked == False)  # noqa: E712
    ).scalars().all()
    for s in sessions:
        s.revoked = True
        db.add(s)
    db.commit()
    return len(sessions)


# ---------------------------------------------------------------------------
# MFA setup
# ---------------------------------------------------------------------------

def start_mfa_setup(db: Session, user: User) -> tuple[str, str]:
    """Generates a new TOTP secret and stores it unconfirmed — is_mfa_enabled
    stays False until verify_mfa_setup succeeds, so a half-finished setup
    never locks the user out."""
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.add(user)
    db.commit()

    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="DermAI Platform")
    return secret, uri


def verify_mfa_setup(db: Session, user: User, code: str) -> None:
    if not user.mfa_secret:
        raise InvalidMFACodeError("No MFA setup in progress for this account")

    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code, valid_window=1):
        raise InvalidMFACodeError("Incorrect authentication code")

    user.is_mfa_enabled = True
    db.add(user)
    db.commit()


def disable_mfa(db: Session, user: User, password: str) -> None:
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect password")

    user.is_mfa_enabled = False
    user.mfa_secret = None
    db.add(user)
    db.commit()
    revoke_all_sessions(db, user.id)  # a leaked+MFA'd token pair from before should not survive this


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

RESET_TOKEN_EXPIRE_MINUTES = 30


def request_password_reset(db: Session, email: str) -> PasswordResetRequestOut:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    generic_message = "If an account with that email exists, a reset link has been sent."
    if not user:
        # Deliberately identical response whether or not the email exists —
        # otherwise this endpoint becomes a way to enumerate registered emails.
        return PasswordResetRequestOut(message=generic_message)

    raw_token = generate_raw_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(reset)
    db.commit()

    # DEV-ONLY: real email delivery is Phase 12 (Notifications). Until then
    # the raw token is returned directly so the flow is testable end-to-end.
    return PasswordResetRequestOut(message=generic_message, dev_reset_token=raw_token)


def confirm_password_reset(db: Session, raw_token: str, new_password: str) -> None:
    token_hash = hash_token(raw_token)
    reset = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if not reset or reset.used or _aware(reset.expires_at) < _utcnow():
        raise InvalidResetTokenError("Invalid or expired reset token")

    user = db.get(User, reset.user_id)
    if not user:
        raise InvalidResetTokenError("Invalid or expired reset token")

    user.hashed_password = hash_password(new_password)
    reset.used = True
    db.add(user)
    db.add(reset)
    db.commit()

    revoke_all_sessions(db, user.id)  # a password change should kill existing sessions
