"""Celery task: runs AI analysis for one uploaded skin image.

The worker process opens its own DB session — it shares nothing with
the web request that queued the job, which may have finished long ago."""
import uuid

import app.db.base  # noqa: F401  (registers every model so relationships resolve)
from app.db.session import SessionLocal
from app.services.prediction_service import run_analysis
from app.tasks.celery_app import celery_app


@celery_app.task(name="predictions.analyze_skin_image")
def analyze_skin_image(image_id: str) -> None:
    db = SessionLocal()
    try:
        run_analysis(db, uuid.UUID(image_id))
    finally:
        db.close()
