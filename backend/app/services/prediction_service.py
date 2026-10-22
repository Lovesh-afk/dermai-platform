"""
Orchestrates AI analysis of a skin image:

  request_analysis()  - called by the API: marks the image QUEUED and
                        hands it to Celery. Returns immediately.
  run_analysis()      - called by the Celery worker: fetches the image,
                        calls the inference service, stores the result.

Status lifecycle:  UPLOADED -> QUEUED_FOR_ANALYSIS -> ANALYZED
                                                   \\-> FAILED (retryable)
"""
import base64
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.logging import logger
from app.models.prediction import Prediction
from app.models.skin_image import SkinImage, SkinImageStatus
from app.services import inference_client, storage_service
from app.services.audit_service import log_audit_event
from app.services.inference_client import InferenceServiceError

GENERIC_FAILURE_MESSAGE = "Analysis failed unexpectedly. Please retry."


class AnalysisNotAllowedError(AppError):
    pass


def enqueue_analysis(image_id: uuid.UUID) -> None:
    """Sends the job to Celery. Kept as its own function so tests can
    swap it out and run without a message broker. Imported lazily to
    avoid a circular import (the task module imports this module)."""
    from app.tasks.prediction_tasks import analyze_skin_image

    analyze_skin_image.delay(str(image_id))


def request_analysis(db: Session, image: SkinImage) -> SkinImage:
    if image.status == SkinImageStatus.QUEUED_FOR_ANALYSIS:
        raise AnalysisNotAllowedError("Analysis is already in progress for this image.")
    if image.status == SkinImageStatus.ANALYZED:
        raise AnalysisNotAllowedError("This image has already been analyzed.")

    image.status = SkinImageStatus.QUEUED_FOR_ANALYSIS
    image.analysis_error = None
    db.commit()

    try:
        enqueue_analysis(image.id)
    except Exception as e:  # broker unreachable — don't leave it "queued" forever
        logger.error("analysis_enqueue_failed", image_id=str(image.id), error=str(e))
        image.status = SkinImageStatus.FAILED
        image.analysis_error = "Couldn't start the analysis. Please retry."
        db.commit()

    db.refresh(image)
    return image


def run_analysis(db: Session, image_id: uuid.UUID) -> None:
    image = db.get(SkinImage, image_id)
    if image is None:
        logger.warning("analysis_image_missing", image_id=str(image_id))
        return

    try:
        content = storage_service.read_file(image.storage_key)
        result = inference_client.predict(content, image.content_type)

        heatmap_bytes = base64.b64decode(result["gradcam_png_base64"])
        heatmap_key, heatmap_url = storage_service.save_file(heatmap_bytes, "gradcam.png", "image/png")

        db.add(Prediction(
            skin_image_id=image.id,
            hospital_id=image.hospital_id,
            predicted_class=result["predicted_class"],
            label=result["label"],
            confidence=result["confidence"],
            all_probabilities=result["all_probabilities"],
            guidance=result["guidance"],
            disclaimer=result["disclaimer"],
            gradcam_storage_key=heatmap_key,
            gradcam_url=heatmap_url,
            model_name=result.get("model_name", "unknown"),
        ))
        image.status = SkinImageStatus.ANALYZED
        image.analysis_error = None
        db.commit()
    except Exception as e:
        db.rollback()
        # Known errors carry a patient-safe message; anything else is
        # logged in full but shown to the patient as a generic message.
        safe_message = str(e) if isinstance(e, InferenceServiceError) else GENERIC_FAILURE_MESSAGE
        logger.error("analysis_failed", image_id=str(image_id), error=repr(e))
        image = db.get(SkinImage, image_id)
        image.status = SkinImageStatus.FAILED
        image.analysis_error = safe_message
        db.commit()
        return

    log_audit_event(
        db, action="skin_image.analyze", hospital_id=image.hospital_id,
        resource_type="SkinImage", resource_id=str(image.id),
    )
