from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import UUIDStr


class NotificationOut(BaseModel):
    id: UUIDStr
    type: str
    title: str
    body: str
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    unread: int
