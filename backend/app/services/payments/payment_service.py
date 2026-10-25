"""
Consultation-fee payments. Lifecycle:

  book (fee > 0)  -> appointment AWAITING_PAYMENT, slot held 15 min, order created
  pay + verify    -> payment PAID, appointment PENDING, doctor notified
  hold expires    -> appointment CANCELLED, payment EXPIRED, slot freed
  cancel (paid)   -> refund per policy: doctor cancels = full refund;
                     patient cancels >= 24h ahead = full refund; later = none

Free consultations never touch this module.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.core.logging import logger
from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.services import notification_service
from app.services.audit_service import log_audit_event
from app.services.payments.providers import PaymentProviderError, get_provider, provider_for


class PaymentError(AppError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def fee_in_paise(doctor: Doctor) -> int:
    """The doctor's fee in paise; 0 means a free consultation."""
    if not doctor.consultation_fee:
        return 0
    return int(round(float(doctor.consultation_fee) * 100))


def rupees(paise: int) -> str:
    return f"₹{paise / 100:,.2f}".replace(".00", "")


# --- Starting a payment -------------------------------------------------------

def start_payment(db: Session, appointment: Appointment, amount_paise: int) -> Payment:
    """Creates the provider order for a freshly booked, unpaid appointment."""
    provider = get_provider()
    order_id = provider.create_order(amount_paise, "INR", receipt=str(appointment.id))
    payment = Payment(
        appointment_id=appointment.id, patient_id=appointment.patient_id, hospital_id=appointment.hospital_id,
        amount_paise=amount_paise, currency="INR", provider=provider.name, provider_order_id=order_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_patient_payment(db: Session, patient: Patient, payment_id: uuid.UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None or payment.patient_id != patient.id:  # someone else's = not found
        raise NotFoundError("Payment not found")
    return payment


def assert_payable(db: Session, payment: Payment) -> Appointment:
    expire_unpaid_holds(db)  # a hold that has just run out must not accept money
    db.refresh(payment)
    appointment = db.get(Appointment, payment.appointment_id)
    if payment.status == PaymentStatus.PAID:
        raise PaymentError("This booking is already paid.")
    if appointment.status != AppointmentStatus.AWAITING_PAYMENT:
        raise PaymentError("This booking is no longer waiting for payment. Please book a new slot.")
    return appointment


# --- Completing a payment -------------------------------------------------------

def confirm_razorpay_payment(db: Session, payment: Payment, order_id: str, provider_payment_id: str, signature: str) -> Payment:
    if payment.provider != "razorpay" or order_id != payment.provider_order_id:
        raise PaymentError("Payment details don't match this booking.")
    if not provider_for("razorpay").verify_payment_signature(order_id, provider_payment_id, signature):
        logger.warning("payment_signature_invalid", payment_id=str(payment.id))
        raise PaymentError("We couldn't verify this payment. If money was deducted, it will be refunded.")
    return _mark_paid(db, payment, provider_payment_id)


def simulate_payment(db: Session, payment: Payment, succeed: bool) -> Payment:
    """Development-only stand-in for a real checkout."""
    if payment.provider != "simulated" or settings.ENVIRONMENT == "production":
        raise PaymentError("Simulated payments aren't available here.")
    assert_payable(db, payment)
    if not succeed:
        payment.status = PaymentStatus.FAILED
        db.commit()
        return payment
    return _mark_paid(db, payment, f"sim_pay_{uuid.uuid4().hex[:16]}")


def _mark_paid(db: Session, payment: Payment, provider_payment_id: str) -> Payment:
    """Idempotent: Razorpay may report the same payment twice (browser
    callback AND webhook). The second report must change nothing."""
    if payment.status == PaymentStatus.PAID:
        return payment

    expire_unpaid_holds(db)
    db.refresh(payment)
    appointment = db.get(Appointment, payment.appointment_id)
    payment.provider_payment_id = provider_payment_id
    payment.paid_at = _now()

    if appointment.status != AppointmentStatus.AWAITING_PAYMENT:
        # Money arrived after the hold expired (or the booking was cancelled):
        # the slot may be someone else's now, so give the money straight back.
        payment.status = PaymentStatus.PAID
        db.commit()
        _refund(db, payment, "Payment arrived after the booking had expired, so it was refunded in full.")
        return payment

    payment.status = PaymentStatus.PAID
    appointment.status = AppointmentStatus.PENDING  # now it's a normal request for the doctor
    appointment.hold_expires_at = None
    db.commit()
    db.refresh(payment)

    log_audit_event(db, action="payment.paid", hospital_id=payment.hospital_id, resource_type="Payment",
                    resource_id=str(payment.id), metadata={"amount_paise": payment.amount_paise})
    patient = db.get(Patient, payment.patient_id)
    notification_service.notify(
        db, patient.user_id, "payment.paid", "Payment received",
        f"We received {rupees(payment.amount_paise)} for your appointment.", "/patient/payments",
        email_text=f"We received your payment of {rupees(payment.amount_paise)}. Your appointment request has been sent to the doctor.",
    )
    notification_service.appointment_booked(db, appointment)  # the doctor only hears about paid bookings
    return payment


def handle_webhook_payment_captured(db: Session, order_id: str, provider_payment_id: str) -> None:
    """Covers patients who paid but closed the browser before our verify
    call ran. The webhook's signature was already checked by the endpoint."""
    payment = db.execute(select(Payment).where(Payment.provider_order_id == order_id)).scalar_one_or_none()
    if payment is None:
        logger.warning("webhook_unknown_order", order_id=order_id)
        return
    _mark_paid(db, payment, provider_payment_id)


# --- Expiry ----------------------------------------------------------------------

def expire_unpaid_holds(db: Session, now: datetime | None = None) -> int:
    """Cancels unpaid bookings whose hold has run out, freeing the slot.
    Run by celery beat every few minutes, and also right before anything
    that depends on slot availability, so an expired hold never blocks."""
    now = now or _now()
    held = db.execute(select(Appointment).where(Appointment.status == AppointmentStatus.AWAITING_PAYMENT)).scalars().all()
    expired = 0
    for appt in held:
        if appt.hold_expires_at is None or _utc(appt.hold_expires_at) > now:
            continue
        appt.status = AppointmentStatus.CANCELLED
        appt.cancellation_reason = "Payment not completed in time"
        appt.hold_expires_at = None
        if appt.payment and appt.payment.status in (PaymentStatus.CREATED, PaymentStatus.FAILED):
            appt.payment.status = PaymentStatus.EXPIRED
        db.commit()
        expired += 1
        patient = db.get(Patient, appt.patient_id)
        notification_service.notify(
            db, patient.user_id, "payment.expired", "Booking expired",
            "Your booking was released because payment wasn't completed in time. You can book a new slot.",
            "/patient/doctors",
        )
    return expired


# --- Cancellation & refunds ------------------------------------------------------

def handle_cancellation(db: Session, appointment: Appointment, cancelled_by: User) -> None:
    """Applies the refund policy when a paid (or unpaid) booking is cancelled."""
    payment = appointment.payment
    if payment is None:
        return
    if payment.status in (PaymentStatus.CREATED, PaymentStatus.FAILED):
        payment.status = PaymentStatus.EXPIRED  # nothing was paid; just close it
        payment.note = "Booking cancelled before payment."
        db.commit()
        return
    if payment.status != PaymentStatus.PAID:
        return

    doctor = db.get(Doctor, appointment.doctor_id)
    if cancelled_by.id == doctor.user_id:
        _refund(db, payment, "Full refund: the doctor cancelled the appointment.")
        return

    notice = _utc(appointment.scheduled_at) - _now()
    if notice >= timedelta(hours=settings.REFUND_CUTOFF_HOURS):
        _refund(db, payment, f"Full refund: cancelled at least {settings.REFUND_CUTOFF_HOURS} hours in advance.")
    else:
        payment.note = f"No refund: cancelled less than {settings.REFUND_CUTOFF_HOURS} hours before the appointment."
        db.commit()


def _refund(db: Session, payment: Payment, note: str) -> None:
    patient = db.get(Patient, payment.patient_id)
    try:
        payment.provider_refund_id = provider_for(payment.provider).refund(payment.provider_payment_id, payment.amount_paise)
    except PaymentProviderError as e:
        # The cancellation itself still stands; the failed refund is recorded
        # (and logged) so it can be retried rather than silently lost.
        logger.error("refund_failed", payment_id=str(payment.id), error=str(e))
        payment.status = PaymentStatus.REFUND_FAILED
        payment.note = "Refund pending: we couldn't process it automatically and will retry."
        db.commit()
        return
    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = _now()
    payment.note = note
    db.commit()
    log_audit_event(db, action="payment.refunded", hospital_id=payment.hospital_id, resource_type="Payment",
                    resource_id=str(payment.id), metadata={"amount_paise": payment.amount_paise})
    notification_service.notify(
        db, patient.user_id, "payment.refunded", "Refund issued",
        f"{rupees(payment.amount_paise)} is being refunded to your original payment method.", "/patient/payments",
        email_text=f"A refund of {rupees(payment.amount_paise)} has been issued to your original payment method. It may take a few business days to appear.",
    )


def list_for_patient(db: Session, patient: Patient) -> list[Payment]:
    return list(db.execute(
        select(Payment).where(Payment.patient_id == patient.id).order_by(Payment.created_at.desc())
    ).scalars().all())
