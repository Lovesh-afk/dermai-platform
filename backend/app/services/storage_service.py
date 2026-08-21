"""
File storage abstraction. Every caller uses save_file()/get_public_url()
and never touches S3 or the filesystem directly — this is what lets us
run entirely on local disk today (no AWS account needed to develop or
demo this project) and switch to real S3/Cloudinary later by changing
only this file, not every place that uploads a file.

Mode is decided by whether AWS_S3_BUCKET is set in settings:
  - Configured  -> uploads go to S3, storage_key is the S3 object key,
                   file_url is a presigned/public S3 URL
  - Not configured (current state, no AWS account yet) -> uploads are
    written to a local directory served via FastAPI's StaticFiles
    mount (see main.py), storage_key is the relative file path,
    file_url is a localhost-servable URL

Local mode is NOT production-safe (files live in the container's
filesystem, lost if the container is recreated without a volume) —
it exists purely so the upload flow is fully testable and demoable
before a real AWS account is wired up. This is called out again in
docs/DECISIONS.md.
"""
import uuid
from pathlib import Path

from app.core.config import settings

LOCAL_UPLOAD_DIR = Path("/app/uploads")
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def is_s3_configured() -> bool:
    return bool(settings.AWS_S3_BUCKET and settings.AWS_ACCESS_KEY_ID)


def save_file(content: bytes, filename: str, content_type: str) -> tuple[str, str]:
    """Returns (storage_key, file_url)."""
    if is_s3_configured():
        return _save_to_s3(content, filename, content_type)
    return _save_to_local_disk(content, filename)


def _save_to_local_disk(content: bytes, filename: str) -> tuple[str, str]:
    ext = Path(filename).suffix or ".bin"
    unique_name = f"{uuid.uuid4()}{ext}"
    dest = LOCAL_UPLOAD_DIR / unique_name
    dest.write_bytes(content)

    storage_key = unique_name
    file_url = f"/uploads/{unique_name}"  # served by the StaticFiles mount in main.py
    return storage_key, file_url


def _save_to_s3(content: bytes, filename: str, content_type: str) -> tuple[str, str]:
    # Imported lazily so boto3 is only required when S3 is actually
    # configured — keeps local dev free of an unnecessary dependency.
    import boto3

    ext = Path(filename).suffix or ".bin"
    key = f"skin-images/{uuid.uuid4()}{ext}"

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    s3.put_object(Bucket=settings.AWS_S3_BUCKET, Key=key, Body=content, ContentType=content_type)

    file_url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
    return key, file_url
