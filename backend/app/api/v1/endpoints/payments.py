"""Consultation-fee payments. Patients act only on their own payments;
the webhook is authenticated by Razorpay's signature instead of a login."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.payment import CheckoutOut, PaymentOut, RazorpayVerifyIn, SimulateIn
from app.services import patient_service
from app.services.payments import payment_service
from app.services.payments.payment_service import PaymentError
from app.services.payments.providers import provider_for, verify_webhook_signature

router = APIRouter(prefix="/payments", tags=["payments"])


def _patient_payment(db: Session, user: User, payment_id: str):
    try:
        patient = patient_service.get_patient_by_user_id(db, user.id)
        return payment_service.get_patient_payment(db, patient, uuid.UUID(payment_id))
    except (NotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")


@router.get("/{payment_id}/checkout", response_model=CheckoutOut)
def get_checkout(payment_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Details to open (or reopen) checkout for an unpaid booking."""
    payment = _patient_payment(db, current_user, payment_id)
    try:
        appointment = payment_service.assert_payable(db, payment)
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    doctor = db.get(Doctor, appointment.doctor_id)
    return CheckoutOut(
        payment_id=payment.id, provider=payment.provider, key_id=provider_for(payment.provider).public_key,
        order_id=payment.provider_order_id, amount_paise=payment.amount_paise, currency=payment.currency,
        expires_at=appointment.hold_expires_at, description=f"Consultation with Dr. {doctor.full_name}",
    )


@router.post("/{payment_id}/verify", response_model=PaymentOut)
def verify_payment(payment_id: str, payload: RazorpayVerifyIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Called by the browser after Razorpay Checkout succeeds. Trusted only
    if Razorpay's signature checks out."""
    payment = _patient_payment(db, current_user, payment_id)
    try:
        payment = payment_service.confirm_razorpay_payment(
            db, payment, payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature
        )
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _out(db, payment)


@router.post("/{payment_id}/simulate", response_model=PaymentOut)
def simulate(payment_id: str, payload: SimulateIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Development only: completes a simulated checkout (no Razorpay keys set)."""
    payment = _patient_payment(db, current_user, payment_id)
    try:
        payment = payment_service.simulate_payment(db, payment, succeed=payload.outcome == "success")
    except PaymentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _out(db, payment)


@router.post("/webhooks/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Server-to-server notice from Razorpay. The signature is checked over
    the exact raw body, before the JSON is even parsed."""
    raw = await request.body()
    if not verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature", "")):
        logger.warning("webhook_signature_invalid")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event = json.loads(raw)
    if event.get("event") == "payment.captured":
        entity = event["payload"]["payment"]["entity"]
        payment_service.handle_webhook_payment_captured(db, entity["order_id"], entity["id"])
    return {"status": "ok"}  # other events are acknowledged and ignored


def _out(db: Session, payment) -> PaymentOut:
    appointment = db.get(Appointment, payment.appointment_id)
    doctor = db.get(Doctor, appointment.doctor_id)
    return PaymentOut(
        id=payment.id, appointment_id=payment.appointment_id, amount_paise=payment.amount_paise,
        currency=payment.currency, status=payment.status, provider=payment.provider, paid_at=payment.paid_at,
        refunded_at=payment.refunded_at, note=payment.note, created_at=payment.created_at,
        doctor_name=doctor.full_name, appointment_time=appointment.scheduled_at,
    )
