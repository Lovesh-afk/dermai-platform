from typing import Literal

from pydantic import BaseModel

from app.schemas.doctor import DoctorProfileOut

Condition = Literal["acne", "eczema", "fungal"]


class RecommendedDoctorOut(BaseModel):
    doctor: DoctorProfileOut
    hospital_name: str
    score: int  # 0-100, see recommendation_service for the formula
    reasons: list[str]


class RecommendationsOut(BaseModel):
    # Which condition the ranking considered, and where it came from:
    # "photo" = latest AI photo analysis, "selected" = chosen by the patient
    condition: Condition | None
    condition_source: Literal["photo", "selected"] | None
    doctors: list[RecommendedDoctorOut]
