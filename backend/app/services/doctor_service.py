import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.user import User
from app.schemas.doctor import DoctorProfileCreate
from app.services.audit_service import log_audit_event


def create_doctor_profile(db: Session, user: User, payload: DoctorProfileCreate) -> Doctor:
    existing = db.execute(select(Doctor).where(Doctor.user_id == user.id)).scalar_one_or_none()
    if existing:
        raise AlreadyExistsError("A doctor profile already exists for this user")

    hospital_id = uuid.UUID(payload.hospital_id)
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise NotFoundError("Hospital not found")

    existing_license = db.execute(select(Doctor).where(Doctor.license_number == payload.license_number)).scalar_one_or_none()
    if existing_license:
        raise AlreadyExistsError("A doctor with this license number is already registered")

    doctor = Doctor(
        user_id=user.id,
        hospital_id=hospital_id,
        specialization=payload.specialization,
        license_number=payload.license_number,
        years_experience=payload.years_experience,
        consultation_fee=payload.consultation_fee,
        bio=payload.bio,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    log_audit_event(
        db, action="doctor_profile.create", user_id=user.id, hospital_id=hospital_id,
        resource_type="Doctor", resource_id=str(doctor.id),
    )
    return doctor


def get_doctor_by_id(db: Session, doctor_id: uuid.UUID) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise NotFoundError("Doctor not found")
    return doctor


def list_doctors_by_hospital(db: Session, hospital_id: uuid.UUID) -> list[Doctor]:
    return list(db.execute(select(Doctor).where(Doctor.hospital_id == hospital_id)).scalars().all())
