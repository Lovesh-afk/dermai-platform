import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.doctor import Doctor
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.medical_record import MedicalRecordCreate
from app.services import notification_service
from app.services.audit_service import log_audit_event
from app.services.patient_service import get_patient_for_doctor


def create_medical_record(db: Session, payload: MedicalRecordCreate, doctor: Doctor) -> MedicalRecord:
    """Only a doctor with a shared appointment history with this
    patient may create a record for them — reuses the same RBAC rule
    as viewing a patient's profile (get_patient_for_doctor), so
    "can see this patient" and "can write about this patient" stay
    consistent instead of drifting into two separate rule sets."""
    patient_id = uuid.UUID(payload.patient_id)
    patient = get_patient_for_doctor(db, patient_id, doctor.id)  # raises NotFoundError / PermissionDeniedError

    record = MedicalRecord(
        hospital_id=doctor.hospital_id,
        patient_id=patient_id,
        doctor_id=doctor.id,
        appointment_id=uuid.UUID(payload.appointment_id) if payload.appointment_id else None,
        diagnosis=payload.diagnosis,
        notes=payload.notes,
        attachment_urls=payload.attachment_urls,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log_audit_event(
        db, action="medical_record.create", user_id=doctor.user_id, hospital_id=record.hospital_id,
        resource_type="MedicalRecord", resource_id=str(record.id),
    )
    notification_service.medical_record_added(db, patient, doctor)
    return record


def list_records_for_patient(db: Session, patient_id: uuid.UUID) -> list[MedicalRecord]:
    return list(
        db.execute(
            select(MedicalRecord).where(MedicalRecord.patient_id == patient_id).order_by(MedicalRecord.created_at.desc())
        ).scalars().all()
    )


def get_record_by_id(db: Session, record_id: uuid.UUID) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if not record:
        raise NotFoundError("Medical record not found")
    return record


def list_records_by_doctor(db: Session, doctor_id: uuid.UUID) -> list[MedicalRecord]:
    return list(
        db.execute(
            select(MedicalRecord).where(MedicalRecord.doctor_id == doctor_id).order_by(MedicalRecord.created_at.desc())
        ).scalars().all()
    )
