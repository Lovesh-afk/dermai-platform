from pydantic import BaseModel, EmailStr

from app.schemas.common import UUIDStr


class PlatformStatsOut(BaseModel):
    total_hospitals: int
    total_users: int
    total_patients: int
    total_doctors: int
    total_appointments: int


class HospitalStatsOut(BaseModel):
    hospital_id: UUIDStr
    total_doctors: int
    total_patients: int
    total_appointments: int
    total_completed_appointments: int


class PromoteToHospitalAdminRequest(BaseModel):
    email: EmailStr


class StaffMemberOut(BaseModel):
    id: UUIDStr
    email: EmailStr
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
