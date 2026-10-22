"""
One AI prediction for one skin image. Kept as its own table (rather
than columns on SkinImage) so the prediction record — which model
produced it, every class probability, the heatmap — is a complete,
auditable artifact on its own.
"""
import uuid
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class Prediction(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "predictions"

    skin_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skin_images.id"), nullable=False, unique=True, index=True
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=True)

    predicted_class: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    all_probabilities: Mapped[dict] = mapped_column(JSON, nullable=False)
    guidance: Mapped[str] = mapped_column(String(1000), nullable=False)
    disclaimer: Mapped[str] = mapped_column(String(1000), nullable=False)

    gradcam_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    gradcam_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
