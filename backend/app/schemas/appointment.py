from datetime import datetime

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus
from app.models.payment import PaymentStatus
from app.schemas.common import UUIDStr


class AppointmentCreate(BaseModel):
    doctor_id: UUIDStr
    scheduled_at: datetime
    reason: str | None = Field(default=None, max_length=1000)


class AppointmentCancel(BaseModel):
    cancellation_reason: str | None = Field(default=None, max_length=500)


class AppointmentStatusUpdate(BaseModel):
    """Doctor-only transition — e.g. pending -> confirmed -> completed,
    or marking a no_show. Cancellation stays on its own endpoint
    (/cancel) since patients can also cancel and it needs a reason."""
    status: AppointmentStatus


class AppointmentOut(BaseModel):
    id: UUIDStr
    hospital_id: UUIDStr
    patient_id: UUIDStr
    doctor_id: UUIDStr
    scheduled_at: datetime
    status: AppointmentStatus
    reason: str | None = None
    cancellation_reason: str | None = None
    hold_expires_at: datetime | None = None  # set while awaiting payment
    payment: "PaymentSummaryOut | None" = None

    model_config = {"from_attributes": True}


class PaymentSummaryOut(BaseModel):
    id: UUIDStr
    status: PaymentStatus
    amount_paise: int
    currency: str
    provider: str

    model_config = {"from_attributes": True}


AppointmentOut.model_rebuild()
