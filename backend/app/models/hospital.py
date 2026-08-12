"""A Hospital is a tenant. Every tenant-scoped table (users, patients,
appointments, etc.) carries a hospital_id FK — see ARCHITECTURE.md for
why we chose row-level multi-tenancy over schema-per-tenant."""
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class Hospital(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "hospitals"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    subscription_tier: Mapped[str] = mapped_column(String(50), default="trial")
    is_active: Mapped[bool] = mapped_column(default=True)
