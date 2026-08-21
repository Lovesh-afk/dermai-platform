import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.patient import Patient
from app.models.skin_image import SkinImage
from app.services import storage_service
from app.services.audit_service import log_audit_event

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class UnsupportedImageTypeError(AppError):
    pass


class ImageTooLargeError(AppError):
    pass


def upload_skin_image(db: Session, patient: Patient, content: bytes, filename: str, content_type: str) -> SkinImage:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedImageTypeError(f"Unsupported image type '{content_type}'. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ImageTooLargeError(f"Image exceeds the {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB limit")

    storage_key, file_url = storage_service.save_file(content, filename, content_type)

    from app.models.user import User

    user = db.get(User, patient.user_id)

    image = SkinImage(
        patient_id=patient.id,
        hospital_id=user.hospital_id if user else None,
        storage_key=storage_key,
        file_url=file_url,
        content_type=content_type,
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    log_audit_event(
        db, action="skin_image.upload", user_id=patient.user_id, hospital_id=image.hospital_id,
        resource_type="SkinImage", resource_id=str(image.id),
    )
    return image


def list_images_for_patient(db: Session, patient_id: uuid.UUID) -> list[SkinImage]:
    return list(
        db.execute(select(SkinImage).where(SkinImage.patient_id == patient_id).order_by(SkinImage.created_at.desc())).scalars().all()
    )
