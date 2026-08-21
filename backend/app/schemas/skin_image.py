from datetime import datetime

from pydantic import BaseModel

from app.models.skin_image import SkinImageStatus
from app.schemas.common import UUIDStr


class SkinImageOut(BaseModel):
    id: UUIDStr
    patient_id: UUIDStr
    file_url: str
    content_type: str
    status: SkinImageStatus
    created_at: datetime

    model_config = {"from_attributes": True}
