from datetime import date

from pydantic import BaseModel, Field


class PatientProfileCreate(BaseModel):
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    known_allergies: str | None = Field(default=None, max_length=500)


class PatientProfileOut(PatientProfileCreate):
    id: str
    user_id: str

    model_config = {"from_attributes": True}
