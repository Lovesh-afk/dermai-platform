"""In-app notifications (the bell). Emails are sent separately and not
stored; this table is the user's notification history."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "notifications"
    # The bell asks "how many unread for this user?" every 30s: index it
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "appointment.confirmed"
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)  # frontend path to open
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Overrides the mixin's database-side timestamp: the bell lists newest
    # first, and two notifications are often created within the same
    # second (e.g. "confirmed" then "completed"). A microsecond-precision
    # time set in Python keeps that order exact on every database.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, server_default=func.now())
