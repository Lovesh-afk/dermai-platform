from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import UUIDStr


class ChatSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    conversation_id: UUIDStr | None = None  # omit to start a new conversation


class ChatSource(BaseModel):
    title: str
    section: str


class ChatMessageOut(BaseModel):
    id: UUIDStr
    role: str
    content: str
    mode: str | None = None
    sources: list[ChatSource] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatConversationOut(BaseModel):
    id: UUIDStr
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatTurnOut(BaseModel):
    conversation_id: UUIDStr
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
