"""
Thin HTTP client for the inference microservice (ai/service). The rest
of the backend calls predict() and never knows TensorFlow exists.

Every failure is converted into InferenceServiceError with a message
that is safe to show a patient — raw connection errors and stack
traces stay in the server logs.
"""
import httpx

from app.core.config import settings
from app.core.exceptions import AppError

REQUEST_TIMEOUT_SECONDS = 60  # CPU inference + Grad-CAM can take a few seconds


class InferenceServiceError(AppError):
    pass


def predict(image_bytes: bytes, content_type: str) -> dict:
    try:
        resp = httpx.post(
            f"{settings.INFERENCE_SERVICE_URL}/predict",
            files={"file": ("image", image_bytes, content_type)},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as e:  # connection refused, DNS failure, timeout...
        raise InferenceServiceError(
            "The analysis service is unavailable right now. Please retry in a minute."
        ) from e

    if resp.status_code == 400:
        raise InferenceServiceError("This file couldn't be read as an image.")
    if resp.status_code != 200:
        raise InferenceServiceError(f"The analysis service returned an error ({resp.status_code}).")
    return resp.json()
