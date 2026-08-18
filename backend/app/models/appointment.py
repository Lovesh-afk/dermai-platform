"""
Appointment status is stored as a plain string column with a Python
Enum for validation at the application layer, rather than a native
Postgres ENUM type — native enums make later "add a new status"
migrations more painful (ALTER TYPE gymnastics) for very little
benefit at this scale. SQLAlchemy's Enum(..., native_enum=False)
gives us the validation without that cost, and it's portable to
SQLite for tests too.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "appointments"

    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False, index=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, native_enum=False, length=20), default=AppointmentStatus.PENDING, nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
