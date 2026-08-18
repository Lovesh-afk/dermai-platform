import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientProfileCreate
from app.services.audit_service import log_audit_event


def create_patient_profile(db: Session, user: User, payload: PatientProfileCreate) -> Patient:
    existing = db.execute(select(Patient).where(Patient.user_id == user.id)).scalar_one_or_none()
    if existing:
        raise AlreadyExistsError("A patient profile already exists for this user")

    patient = Patient(user_id=user.id, **payload.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)

    log_audit_event(
        db, action="patient_profile.create", user_id=user.id, hospital_id=user.hospital_id,
        resource_type="Patient", resource_id=str(patient.id),
    )
    return patient


def get_patient_by_user_id(db: Session, user_id: uuid.UUID) -> Patient:
    patient = db.execute(select(Patient).where(Patient.user_id == user_id)).scalar_one_or_none()
    if not patient:
        raise NotFoundError("No patient profile found for this user")
    return patient


def get_patient_by_id(db: Session, patient_id: uuid.UUID) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")
    return patient
