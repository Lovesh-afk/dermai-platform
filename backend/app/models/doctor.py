"""A Doctor extends a User with professional/clinical profile fields.
Same rationale as Patient: keeps User lean, and these fields are
meaningless for a patient or hospital-admin account."""
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class Doctor(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "doctors"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)

    specialization: Mapped[str] = mapped_column(String(255), nullable=False, default="Dermatology")
    license_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    years_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    consultation_fee: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    is_accepting_appointments: Mapped[bool] = mapped_column(default=True)

    # The doctor's account, loaded alongside (selectin) so listing doctors
    # with names never triggers one extra query per doctor.
    user: Mapped["User"] = relationship("User", lazy="selectin")  # noqa: F821

    @property
    def full_name(self) -> str | None:
        return self.user.full_name if self.user else None
