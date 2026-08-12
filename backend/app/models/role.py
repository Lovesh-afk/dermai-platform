"""Roles are per-hospital (except platform-level SUPER_ADMIN) so a
hospital admin can define custom staff roles without a code deploy —
see ARCHITECTURE.md 'RBAC' decision."""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class Role(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. ["patients:read", "appointments:write", "billing:read"]
    # JSON (not Postgres ARRAY) so this works identically in SQLite for
    # fast unit tests and in Postgres in production — one model, no
    # dialect-specific branching.
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True
    )  # null => platform-level role (e.g. SUPER_ADMIN)
