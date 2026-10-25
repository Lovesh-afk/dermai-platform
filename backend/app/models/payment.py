"""
One payment for one appointment's consultation fee.

Money is stored as an integer number of paise (1 rupee = 100 paise),
never as a float: floats can't represent amounts like 0.10 exactly, and
payment providers (Razorpay included) work in the smallest currency unit.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class PaymentStatus(str, enum.Enum):
    CREATED = "created"            # order created, patient hasn't paid yet
    PAID = "paid"                  # verified payment
    FAILED = "failed"              # attempt failed; patient can retry until the hold expires
    EXPIRED = "expired"            # hold ran out before payment
    REFUNDED = "refunded"          # full refund issued
    REFUND_FAILED = "refund_failed"  # refund attempt failed; needs attention


class Payment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payments"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, unique=True, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)

    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, native_enum=False, length=20), nullable=False, default=PaymentStatus.CREATED
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # "razorpay" | "simulated"
    provider_order_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    provider_refund_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Plain-language explanation shown to the patient, e.g. why no refund was given
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
