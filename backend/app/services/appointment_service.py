import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate
from app.services.audit_service import log_audit_event


class DoctorUnavailableError(AppError):
    pass


class SlotConflictError(AppError):
    pass


def book_appointment(db: Session, patient: Patient, payload: AppointmentCreate) -> Appointment:
    doctor_id = uuid.UUID(payload.doctor_id)
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise NotFoundError("Doctor not found")
    if not doctor.is_accepting_appointments:
        raise DoctorUnavailableError("This doctor is not currently accepting appointments")

    # Simple double-booking guard: same doctor, same exact timestamp,
    # not already cancelled. A real scheduling system (slot durations,
    # buffer times) is a reasonable Phase 11 enhancement — this is the
    # minimum needed so the schema itself enforces something meaningful.
    conflict = db.execute(
        select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at == payload.scheduled_at,
            Appointment.status.notin_([AppointmentStatus.CANCELLED]),
        )
    ).scalar_one_or_none()
    if conflict:
        raise SlotConflictError("This doctor already has an appointment at that time")

    appointment = Appointment(
        hospital_id=doctor.hospital_id,
        patient_id=patient.id,
        doctor_id=doctor_id,
        scheduled_at=payload.scheduled_at,
        reason=payload.reason,
        status=AppointmentStatus.PENDING,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    log_audit_event(
        db, action="appointment.book", user_id=patient.user_id, hospital_id=doctor.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id),
    )
    return appointment


def cancel_appointment(db: Session, appointment_id: uuid.UUID, cancellation_reason: str | None, cancelling_user_id: uuid.UUID) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = cancellation_reason
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    log_audit_event(
        db, action="appointment.cancel", user_id=cancelling_user_id, hospital_id=appointment.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id),
    )
    return appointment


def list_appointments_for_patient(db: Session, patient_id: uuid.UUID) -> list[Appointment]:
    return list(db.execute(select(Appointment).where(Appointment.patient_id == patient_id)).scalars().all())


def list_appointments_for_doctor(db: Session, doctor_id: uuid.UUID) -> list[Appointment]:
    return list(db.execute(select(Appointment).where(Appointment.doctor_id == doctor_id)).scalars().all())


def update_appointment_status(db: Session, appointment_id: uuid.UUID, new_status: AppointmentStatus, doctor: Doctor) -> Appointment:
    """Doctor-only transition (confirm/complete/no-show). Cancellation
    has its own endpoint since either party can do it and it needs a
    reason — this one is specifically the doctor managing their queue."""
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")
    if appointment.doctor_id != doctor.id:
        raise PermissionDeniedError("This appointment does not belong to you")

    appointment.status = new_status
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    log_audit_event(
        db, action="appointment.status_update", user_id=doctor.user_id, hospital_id=appointment.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id), metadata={"new_status": new_status.value},
    )
    return appointment


def get_appointment_by_id(db: Session, appointment_id: uuid.UUID) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")
    return appointment
