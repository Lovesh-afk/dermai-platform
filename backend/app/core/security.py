"""
Password hashing and JWT issuance/verification.
Access tokens are short-lived; refresh tokens are longer-lived and
are stored hashed server-side (see UserSession model) so a leaked
refresh token can be revoked — logout/revocation is meaningless
without this.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MFA_PENDING_TOKEN_EXPIRE_MINUTES = 5  # short-lived: just enough to enter the TOTP code


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def generate_raw_token() -> str:
    """A high-entropy random token for refresh tokens / reset tokens
    that get stored server-side as a hash (not JWTs — no need for
    them to be self-describing, and hashing a random token is simpler
    to reason about for revocation than parsing/validating a JWT)."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """SHA-256 is fine here (not bcrypt) — these tokens are already
    high-entropy random values, not human-guessable passwords, so we
    don't need bcrypt's deliberate slowness, just collision resistance."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _create_jwt(subject: str, expires_delta: timedelta, token_type: Literal["access", "mfa_pending"], extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str, hospital_id: str | None = None) -> str:
    return _create_jwt(
        subject=subject,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        extra_claims={"role": role, "hospital_id": hospital_id},
    )


def create_mfa_pending_token(subject: str) -> str:
    """Issued right after password verification when MFA is enabled.
    Proves "this person already knows the password" without granting
    any actual access — the only thing it's accepted for is the
    /auth/mfa/login-verify endpoint."""
    return _create_jwt(
        subject=subject,
        expires_delta=timedelta(minutes=MFA_PENDING_TOKEN_EXPIRE_MINUTES),
        token_type="mfa_pending",
    )


def decode_jwt(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# Backwards-compatible alias used elsewhere in the codebase
decode_token = decode_jwt
