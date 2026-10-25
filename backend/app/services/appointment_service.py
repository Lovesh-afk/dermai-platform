import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, NotFoundError, PermissionDeniedError
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate
from app.services import notification_service, scheduling_service
from app.services.payments import payment_service
from app.services.payments.providers import PaymentProviderError
from app.services.audit_service import log_audit_event


class DoctorUnavailableError(AppError):
    pass


class SlotConflictError(AppError):
    pass


class SlotUnavailableError(AppError):
    """Outside working hours, misaligned, or in the past."""


class PaymentUnavailableError(AppError):
    """The payment provider couldn't create an order; the slot was released."""


class NotCancellableError(AppError):
    """Only pending or confirmed appointments can be cancelled."""


def book_appointment(db: Session, patient: Patient, payload: AppointmentCreate) -> Appointment:
    doctor_id = uuid.UUID(payload.doctor_id)
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise NotFoundError("Doctor not found")
    if not doctor.is_accepting_appointments:
        raise DoctorUnavailableError("This doctor is not currently accepting appointments")

    # Always store UTC, whatever offset the client sent
    scheduled_at = scheduling_service._utc(payload.scheduled_at)
    payment_service.expire_unpaid_holds(db)  # an expired hold must not block this slot

    problem = scheduling_service.booking_problem(db, doctor, scheduled_at)
    if problem:
        raise SlotUnavailableError(problem)

    if _slot_is_taken(db, doctor_id, scheduled_at):
        raise SlotConflictError("Sorry, that slot was just booked. Please choose another time.")

    fee = payment_service.fee_in_paise(doctor)
    appointment = Appointment(
        hospital_id=doctor.hospital_id,
        patient_id=patient.id,
        doctor_id=doctor_id,
        scheduled_at=scheduled_at,
        reason=payload.reason,
        status=AppointmentStatus.AWAITING_PAYMENT if fee else AppointmentStatus.PENDING,
        hold_expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PAYMENT_HOLD_MINUTES) if fee else None,
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race: another request booked this slot between our check
        # and our insert. The unique index on appointments caught it.
        db.rollback()
        raise SlotConflictError("Sorry, that slot was just booked. Please choose another time.")
    db.refresh(appointment)

    log_audit_event(
        db, action="appointment.book", user_id=patient.user_id, hospital_id=doctor.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id),
    )
    if not fee:
        notification_service.appointment_booked(db, appointment)
        return appointment

    # Paid consultation: the doctor is only notified once payment succeeds
    try:
        payment_service.start_payment(db, appointment, fee)
    except PaymentProviderError as e:
        appointment.status = AppointmentStatus.CANCELLED  # release the slot straight away
        appointment.cancellation_reason = "Payment service unavailable"
        appointment.hold_expires_at = None
        db.commit()
        raise PaymentUnavailableError("We couldn't start the payment. Please try again in a moment.") from e
    db.refresh(appointment)
    return appointment


def _slot_is_taken(db: Session, doctor_id: uuid.UUID, scheduled_at) -> bool:
    return db.execute(
        select(Appointment.id).where(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at == scheduled_at,
            Appointment.status.in_(scheduling_service.ACTIVE_STATUSES),
        )
    ).first() is not None


def cancel_appointment(db: Session, appointment_id: uuid.UUID, cancellation_reason: str | None, cancelling_user) -> Appointment:
    """Either party can cancel: the appointment's own patient or doctor.
    Anyone else gets "not found", so appointment IDs can't be probed.
    (Before Phase 12 there was no ownership check at all, so any logged-in
    user could cancel any appointment by ID.)"""
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")

    patient = db.get(Patient, appointment.patient_id)
    doctor = db.get(Doctor, appointment.doctor_id)
    if cancelling_user.id not in (patient.user_id, doctor.user_id):
        raise NotFoundError("Appointment not found")
    if appointment.status not in scheduling_service.ACTIVE_STATUSES:
        raise NotCancellableError(f"A {appointment.status.value.replace('_', ' ')} appointment can't be cancelled.")

    was_unpaid_hold = appointment.status == AppointmentStatus.AWAITING_PAYMENT
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = cancellation_reason
    appointment.hold_expires_at = None
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    payment_service.handle_cancellation(db, appointment, cancelling_user)

    log_audit_event(
        db, action="appointment.cancel", user_id=cancelling_user.id, hospital_id=appointment.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id),
    )
    if not was_unpaid_hold:  # the doctor never saw an unpaid hold, so there's no one to tell
        notification_service.appointment_cancelled(db, appointment, cancelling_user)
    db.refresh(appointment)
    return appointment


def list_appointments_for_patient(db: Session, patient_id: uuid.UUID) -> list[Appointment]:
    return list(db.execute(select(Appointment).where(Appointment.patient_id == patient_id)).scalars().all())


def list_appointments_for_doctor(db: Session, doctor_id: uuid.UUID) -> list[Appointment]:
    """Unpaid holds aren't real requests yet, so doctors don't see them."""
    return list(db.execute(select(Appointment).where(
        Appointment.doctor_id == doctor_id, Appointment.status != AppointmentStatus.AWAITING_PAYMENT
    )).scalars().all())


def update_appointment_status(db: Session, appointment_id: uuid.UUID, new_status: AppointmentStatus, doctor: Doctor) -> Appointment:
    """Doctor-only transition (confirm/complete/no-show). Cancellation
    has its own endpoint since either party can do it and it needs a
    reason — this one is specifically the doctor managing their queue."""
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")
    if appointment.doctor_id != doctor.id:
        raise PermissionDeniedError("This appointment does not belong to you")
    if appointment.status == AppointmentStatus.AWAITING_PAYMENT:
        raise NotCancellableError("This booking hasn't been paid yet.")

    appointment.status = new_status
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    log_audit_event(
        db, action="appointment.status_update", user_id=doctor.user_id, hospital_id=appointment.hospital_id,
        resource_type="Appointment", resource_id=str(appointment.id), metadata={"new_status": new_status.value},
    )
    notification_service.appointment_status_changed(db, appointment)
    return appointment


def get_appointment_by_id(db: Session, appointment_id: uuid.UUID) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")
    return appointment
