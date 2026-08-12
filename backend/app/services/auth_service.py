"""
All auth business logic lives here, not in the endpoint. This is the
unit-test surface — endpoints stay thin and are covered by integration
tests instead.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, InvalidCredentialsError, NotFoundError
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.hospital import Hospital
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import TokenPair, UserLogin, UserRegister


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
    else:
        role_name = "PATIENT"

    # Default PATIENT role is scoped per-hospital (or global if self-signup) — seeded via migration/seed script.
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


def authenticate_user(db: Session, payload: UserLogin) -> User:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password")
    if not user.is_active:
        raise InvalidCredentialsError("This account has been deactivated")
    return user


def issue_tokens(db: Session, user: User) -> TokenPair:
    role = db.get(Role, user.role_id)
    access = create_access_token(subject=str(user.id), role=role.name, hospital_id=str(user.hospital_id) if user.hospital_id else None)
    refresh = create_refresh_token(subject=str(user.id))
    return TokenPair(access_token=access, refresh_token=refresh)


def refresh_access_token(db: Session, refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise InvalidCredentialsError("Invalid or expired refresh token")

    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise InvalidCredentialsError("Invalid or expired refresh token")

    return issue_tokens(db, user)
