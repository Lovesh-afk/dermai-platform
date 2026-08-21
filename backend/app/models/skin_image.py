"""
A SkinImage is a patient-uploaded photo, tracked from upload through
AI analysis. status is what Phase 7/8 (the AI model + prediction API)
will move through UPLOADED -> QUEUED -> ANALYZED as the pipeline
picks it up — the column exists now so that pipeline has something to
attach to without a schema change later.

file_url intentionally stores a servable URL regardless of backend
(local disk in dev, S3/Cloudinary in production) — see
services/storage_service.py for the abstraction that makes this work
identically either way.
"""
import enum
import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class SkinImageStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED_FOR_ANALYSIS = "queued_for_analysis"
    ANALYZED = "analyzed"


class SkinImage(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "skin_images"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)

    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)  # local path or S3 object key
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)   # servable URL either way
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[SkinImageStatus] = mapped_column(
        Enum(SkinImageStatus, native_enum=False, length=30), default=SkinImageStatus.UPLOADED, nullable=False
    )
