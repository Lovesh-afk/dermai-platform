from pydantic import BaseModel, Field
from app.schemas.common import UUIDStr


class DoctorProfileCreate(BaseModel):
    hospital_id: UUIDStr
    specialization: str = Field(default="Dermatology", max_length=255)
    license_number: str = Field(max_length=100)
    years_experience: int | None = None
    consultation_fee: float | None = None
    bio: str | None = Field(default=None, max_length=2000)


class DoctorProfileOut(BaseModel):
    id: UUIDStr
    user_id: UUIDStr
    hospital_id: UUIDStr
    specialization: str
    license_number: str
    years_experience: int | None = None
    consultation_fee: float | None = None
    bio: str | None = None
    is_accepting_appointments: bool

    model_config = {"from_attributes": True}


class DoctorProfileUpdate(BaseModel):
    """All fields optional — only what's provided gets updated
    (see doctor_service.update_doctor_profile's use of
    model_dump(exclude_unset=True))."""
    specialization: str | None = Field(default=None, max_length=255)
    years_experience: int | None = None
    consultation_fee: float | None = None
    bio: str | None = Field(default=None, max_length=2000)
    is_accepting_appointments: bool | None = None
