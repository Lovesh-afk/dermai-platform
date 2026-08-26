import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError, PermissionDeniedError
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


def get_patient_for_doctor(db: Session, patient_id: uuid.UUID, doctor_id: uuid.UUID) -> Patient:
    """A doctor may only view a patient's profile if they share at
    least one appointment — this is the RBAC boundary that keeps the
    Doctor Portal from becoming a way to browse every patient in the
    system. Once medical-record access needs finer rules (e.g. a
    doctor covering for a colleague), this is the function to extend."""
    from app.models.appointment import Appointment

    patient = get_patient_by_id(db, patient_id)

    shared_appointment = db.execute(
        select(Appointment).where(Appointment.patient_id == patient_id, Appointment.doctor_id == doctor_id)
    ).scalar_one_or_none()
    if not shared_appointment:
        raise PermissionDeniedError("You do not have an appointment with this patient")

    return patient


def list_patients_for_doctor(db: Session, doctor_id: uuid.UUID) -> list[Patient]:
    """Distinct patients who have at least one appointment (of any
    status) with this doctor — this is the doctor's "patient list"."""
    from app.models.appointment import Appointment

    patient_ids = db.execute(
        select(Appointment.patient_id).where(Appointment.doctor_id == doctor_id).distinct()
    ).scalars().all()
    if not patient_ids:
        return []
    return list(db.execute(select(Patient).where(Patient.id.in_(patient_ids))).scalars().all())
