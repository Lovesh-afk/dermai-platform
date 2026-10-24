"""A doctor's weekly working hours: one row per block, e.g. Monday
09:00-13:00 and Monday 14:00-18:00. Times are wall-clock times in the
hospital's time zone. A doctor with no rows uses the default hours
(see scheduling_service.DEFAULT_WEEKLY_HOURS)."""
import uuid
from datetime import time

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class DoctorAvailability(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "doctor_availability"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
