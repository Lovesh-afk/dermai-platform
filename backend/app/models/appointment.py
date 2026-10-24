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

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# Statuses that occupy a slot. Stored by enum NAME ("PENDING"), which is
# what the partial index below must match.
_ACTIVE_STATUSES_SQL = "status IN ('PENDING', 'CONFIRMED')"


class Appointment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        # One active booking per doctor per time. The app checks this too,
        # but only the database can stop two simultaneous requests from
        # both grabbing the same slot (a race condition).
        Index(
            "uq_appointments_doctor_active_slot", "doctor_id", "scheduled_at", unique=True,
            postgresql_where=text(_ACTIVE_STATUSES_SQL), sqlite_where=text(_ACTIVE_STATUSES_SQL),
        ),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=False, index=True)

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, native_enum=False, length=20), default=AppointmentStatus.PENDING, nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Set once the 24-hour reminder has gone out, so it's never sent twice
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
