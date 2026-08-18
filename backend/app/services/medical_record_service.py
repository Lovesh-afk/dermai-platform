import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.medical_record import MedicalRecordCreate
from app.services.audit_service import log_audit_event


def create_medical_record(db: Session, payload: MedicalRecordCreate, created_by_user_id: uuid.UUID) -> MedicalRecord:
    patient_id = uuid.UUID(payload.patient_id)
    patient = db.get(Patient, patient_id)
    if not patient:
        raise NotFoundError("Patient not found")

    record = MedicalRecord(
        hospital_id=_hospital_id_for_patient(db, patient),
        patient_id=patient_id,
        doctor_id=uuid.UUID(payload.doctor_id) if payload.doctor_id else None,
        appointment_id=uuid.UUID(payload.appointment_id) if payload.appointment_id else None,
        diagnosis=payload.diagnosis,
        notes=payload.notes,
        attachment_urls=payload.attachment_urls,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log_audit_event(
        db, action="medical_record.create", user_id=created_by_user_id, hospital_id=record.hospital_id,
        resource_type="MedicalRecord", resource_id=str(record.id),
    )
    return record


def _hospital_id_for_patient(db: Session, patient: Patient) -> uuid.UUID:
    from app.models.user import User

    user = db.get(User, patient.user_id)
    return user.hospital_id
