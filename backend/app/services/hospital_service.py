"""
Hospital creation is now SUPER_ADMIN-only (locked down in Phase 6 —
see api/v1/endpoints/hospitals.py). Before this phase it was
deliberately open with no auth, which was fine as a temporary
bootstrap measure but never meant to stay that way — see
docs/DECISIONS.md for the full history of that decision.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.hospital import Hospital
from app.models.role import Role
from app.schemas.hospital import HospitalCreate, HospitalUpdate
from app.services.audit_service import log_audit_event

# Roles seeded automatically for every new hospital. PATIENT is
# required for registration to work at all (see auth_service.
# register_user). DOCTOR and HOSPITAL_ADMIN are seeded alongside it
# so a hospital is immediately usable end-to-end the moment it's
# created, not just for patients.
DEFAULT_HOSPITAL_ROLES = [
    ("PATIENT", ["appointments:read", "appointments:write"]),
    ("DOCTOR", ["appointments:read", "appointments:write", "medical_records:write"]),
    ("HOSPITAL_ADMIN", ["hospital:manage_staff", "hospital:view_stats"]),
]


def ensure_hospital_roles(db: Session, hospital_id: uuid.UUID) -> list[str]:
    """Creates any of DEFAULT_HOSPITAL_ROLES missing for this hospital.
    Idempotent: roles that already exist are left untouched, so it's
    safe to call any number of times.

    Exists because hospitals created before Phase 6 only got a PATIENT
    role, so promoting a HOSPITAL_ADMIN there failed with "role is not
    seeded". Returns the names of roles it created (empty if none)."""
    existing = set(
        db.execute(select(Role.name).where(Role.hospital_id == hospital_id)).scalars().all()
    )
    created = []
    for role_name, permissions in DEFAULT_HOSPITAL_ROLES:
        if role_name not in existing:
            db.add(Role(name=role_name, permissions=permissions, hospital_id=hospital_id))
            created.append(role_name)
    if created:
        db.commit()
    return created


def create_hospital(db: Session, payload: HospitalCreate, created_by_user_id: uuid.UUID | None) -> Hospital:
    existing = db.execute(select(Hospital).where(Hospital.slug == payload.slug)).scalar_one_or_none()
    if existing:
        raise AlreadyExistsError(f"A hospital with slug '{payload.slug}' already exists")

    hospital = Hospital(name=payload.name, slug=payload.slug)
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    ensure_hospital_roles(db, hospital.id)

    log_audit_event(
        db, action="hospital.create", user_id=created_by_user_id, hospital_id=hospital.id,
        resource_type="Hospital", resource_id=str(hospital.id),
    )
    return hospital


def list_hospitals(db: Session, include_inactive: bool = False) -> list[Hospital]:
    query = select(Hospital)
    if not include_inactive:
        query = query.where(Hospital.is_active == True)  # noqa: E712
    return list(db.execute(query).scalars().all())


def get_hospital_by_id(db: Session, hospital_id: uuid.UUID) -> Hospital:
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise NotFoundError("Hospital not found")
    return hospital


def update_hospital(db: Session, hospital_id: uuid.UUID, payload: HospitalUpdate, updated_by_user_id: uuid.UUID) -> Hospital:
    hospital = get_hospital_by_id(db, hospital_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(hospital, field, value)
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    log_audit_event(
        db, action="hospital.update", user_id=updated_by_user_id, hospital_id=hospital.id,
        resource_type="Hospital", resource_id=str(hospital.id), metadata={"fields": list(updates.keys())},
    )
    return hospital
