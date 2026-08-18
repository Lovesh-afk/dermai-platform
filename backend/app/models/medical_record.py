"""
A MedicalRecord captures the clinical outcome of a visit — diagnosis,
doctor's notes, and (later, Phase 4/7) links to uploaded images and
AI prediction results. appointment_id is nullable because a record
can also come from an async AI-only flow with no booked appointment
(e.g. patient uploads a photo and gets a preliminary read before ever
seeing a doctor).
"""
import uuid
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class MedicalRecord(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "medical_records"

    hospital_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("doctors.id"), nullable=True)
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)

    diagnosis: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(4000), nullable=True)
    # List of S3/Cloudinary URLs — actual upload wiring lands in Phase 4.
    attachment_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
