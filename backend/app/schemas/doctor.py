from pydantic import BaseModel, Field


class DoctorProfileCreate(BaseModel):
    hospital_id: str
    specialization: str = Field(default="Dermatology", max_length=255)
    license_number: str = Field(max_length=100)
    years_experience: int | None = None
    consultation_fee: float | None = None
    bio: str | None = Field(default=None, max_length=2000)


class DoctorProfileOut(BaseModel):
    id: str
    user_id: str
    hospital_id: str
    specialization: str
    license_number: str
    years_experience: int | None = None
    consultation_fee: float | None = None
    bio: str | None = None
    is_accepting_appointments: bool

    model_config = {"from_attributes": True}
