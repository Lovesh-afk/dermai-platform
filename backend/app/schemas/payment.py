from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus
from app.schemas.common import UUIDStr


class CheckoutOut(BaseModel):
    """What the browser needs to open checkout. Contains the PUBLIC key
    only; the secret never leaves the server."""
    payment_id: UUIDStr
    provider: str               # "razorpay" | "simulated"
    key_id: str | None          # Razorpay public key (None when simulated)
    order_id: str
    amount_paise: int
    currency: str
    expires_at: datetime | None
    description: str


class RazorpayVerifyIn(BaseModel):
    razorpay_order_id: str = Field(max_length=100)
    razorpay_payment_id: str = Field(max_length=100)
    razorpay_signature: str = Field(max_length=200)


class SimulateIn(BaseModel):
    outcome: Literal["success", "failure"]


class PaymentOut(BaseModel):
    id: UUIDStr
    appointment_id: UUIDStr
    amount_paise: int
    currency: str
    status: PaymentStatus
    provider: str
    paid_at: datetime | None = None
    refunded_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    doctor_name: str | None = None
    appointment_time: datetime | None = None
