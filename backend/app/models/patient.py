"""
A Patient extends a User with medical-context profile fields. Split
from User (rather than adding these columns to User directly) because
doctors/admins never need date_of_birth/emergency_contact/etc., and
keeping them separate means the User table stays lean for every role.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class Patient(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Free-text for now (e.g. "penicillin, peanuts") — a structured
    # allergies/conditions table is worth revisiting once the AI
    # prediction pipeline (Phase 7) needs to cross-reference them.
    known_allergies: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
