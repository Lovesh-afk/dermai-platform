"""
Hospital creation is deliberately open (no auth required) for now —
there's no Admin Portal yet (Phase 6) to gate it behind a real
SUPER_ADMIN check, and without *some* way to create a hospital, the
whole app is unusable outside of tests that reach into the database
directly. This is flagged clearly as temporary: Phase 6 will lock
this down to SUPER_ADMIN-only and this open version goes away then.
See docs/DECISIONS.md.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.hospital import Hospital
from app.models.role import Role
from app.schemas.hospital import HospitalCreate
from app.services.audit_service import log_audit_event


def create_hospital(db: Session, payload: HospitalCreate) -> Hospital:
    existing = db.execute(select(Hospital).where(Hospital.slug == payload.slug)).scalar_one_or_none()
    if existing:
        raise AlreadyExistsError(f"A hospital with slug '{payload.slug}' already exists")

    hospital = Hospital(name=payload.name, slug=payload.slug)
    db.add(hospital)
    db.commit()
    db.refresh(hospital)

    # A hospital is useless for registration until it has a PATIENT
    # role to assign — see auth_service.register_user, which looks
    # this up by (name="PATIENT", hospital_id=<this hospital>).
    db.add(Role(name="PATIENT", permissions=["appointments:read", "appointments:write"], hospital_id=hospital.id))
    db.commit()

    log_audit_event(db, action="hospital.create", hospital_id=hospital.id, resource_type="Hospital", resource_id=str(hospital.id))
    return hospital


def list_hospitals(db: Session) -> list[Hospital]:
    return list(db.execute(select(Hospital).where(Hospital.is_active == True)).scalars().all())  # noqa: E712


def get_hospital_by_id(db: Session, hospital_id: uuid.UUID) -> Hospital:
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise NotFoundError("Hospital not found")
    return hospital
