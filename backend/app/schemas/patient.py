from datetime import date

from pydantic import BaseModel, Field
from app.schemas.common import UUIDStr


class PatientProfileCreate(BaseModel):
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    known_allergies: str | None = Field(default=None, max_length=500)


class PatientProfileOut(PatientProfileCreate):
    id: UUIDStr
    user_id: UUIDStr

    model_config = {"from_attributes": True}


class PatientProfileUpdate(BaseModel):
    """All fields optional — mirrors DoctorProfileUpdate's pattern
    (see doctor.py). Added alongside the frontend build once it
    became clear patients need to edit their profile after creating
    it, not just view it."""
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    known_allergies: str | None = Field(default=None, max_length=500)
