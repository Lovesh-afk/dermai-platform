from datetime import datetime

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    doctor_id: str
    scheduled_at: datetime
    reason: str | None = Field(default=None, max_length=1000)


class AppointmentCancel(BaseModel):
    cancellation_reason: str | None = Field(default=None, max_length=500)


class AppointmentOut(BaseModel):
    id: str
    hospital_id: str
    patient_id: str
    doctor_id: str
    scheduled_at: datetime
    status: AppointmentStatus
    reason: str | None = None
    cancellation_reason: str | None = None

    model_config = {"from_attributes": True}
