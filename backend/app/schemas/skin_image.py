from datetime import datetime

from pydantic import BaseModel

from app.models.skin_image import SkinImageStatus
from app.schemas.common import UUIDStr


class PredictionOut(BaseModel):
    predicted_class: str
    label: str
    confidence: float
    all_probabilities: dict[str, float]
    guidance: str
    disclaimer: str
    gradcam_url: str
    model_name: str
    created_at: datetime

    # "model_name" starts with Pydantic's reserved "model_" prefix; allow it
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class SkinImageOut(BaseModel):
    id: UUIDStr
    patient_id: UUIDStr
    file_url: str
    content_type: str
    status: SkinImageStatus
    analysis_error: str | None = None
    prediction: PredictionOut | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
