"""Chat history. A user's conversations are private to them: every
query is filtered by user_id, and other users get a 404."""
import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class ChatConversation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "chat_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class ChatMessage(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Explicit ordering: a question and its answer are saved within the
    # same second, so timestamps alone can't be trusted to order them.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # How the assistant answered: ai | knowledge_base | emergency | out_of_scope
    mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
