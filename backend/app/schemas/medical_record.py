from pydantic import BaseModel, Field
from app.schemas.common import UUIDStr


class MedicalRecordCreate(BaseModel):
    patient_id: UUIDStr
    doctor_id: UUIDStr | None = None
    appointment_id: UUIDStr | None = None
    diagnosis: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    attachment_urls: list[str] = Field(default_factory=list)


class MedicalRecordOut(BaseModel):
    id: UUIDStr
    hospital_id: UUIDStr
    patient_id: UUIDStr
    doctor_id: UUIDStr | None = None
    appointment_id: UUIDStr | None = None
    diagnosis: str | None = None
    notes: str | None = None
    attachment_urls: list[str] = []

    model_config = {"from_attributes": True}
