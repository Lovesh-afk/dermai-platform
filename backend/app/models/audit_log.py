"""
Append-only audit trail. Healthcare software needs to answer "who
accessed/changed what, and when" — this table is written to by a
service-layer helper (log_audit_event) from anywhere sensitive data
is touched, starting with auth events in Phase 2's services and
expanding as patient data endpoints land in Phase 4+.

Deliberately NOT a TimestampMixin/UUIDPKMixin subclass with an
updated_at — audit rows are write-once and never updated, so having
an updated_at column would be misleading.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. "login", "medical_record.view"
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "MedicalRecord"
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)  # freeform: IP, user agent, before/after, etc.
