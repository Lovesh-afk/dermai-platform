from pydantic import BaseModel, Field
from app.schemas.common import UUIDStr


class MedicalRecordCreate(BaseModel):
    """doctor_id is deliberately NOT part of this payload — the
    creating doctor is always taken from the authenticated user
    (see api/v1/endpoints/medical_records.py), never from client
    input, so a doctor can't write a record and attribute it to a
    different doctor."""
    patient_id: UUIDStr
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
