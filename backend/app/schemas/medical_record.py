from pydantic import BaseModel, Field


class MedicalRecordCreate(BaseModel):
    patient_id: str
    doctor_id: str | None = None
    appointment_id: str | None = None
    diagnosis: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=4000)
    attachment_urls: list[str] = Field(default_factory=list)


class MedicalRecordOut(BaseModel):
    id: str
    hospital_id: str
    patient_id: str
    doctor_id: str | None = None
    appointment_id: str | None = None
    diagnosis: str | None = None
    notes: str | None = None
    attachment_urls: list[str] = []

    model_config = {"from_attributes": True}
