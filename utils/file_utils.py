import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

try:
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import storage
except ImportError:
    DefaultCredentialsError = None
    storage = None

from app.config import settings

BUCKET_NAME = settings.gcs_base_url.split("/")[-1]
gcs_client: Any | None = None


def get_gcs_client() -> Any:
    global gcs_client
    if storage is None:
        raise RuntimeError(
            "Google Cloud Storage is enabled, but google-cloud-storage is not "
            "installed. Set USE_CLOUD_STORAGE=false for local file storage or "
            "install google-cloud-storage."
        )
    if gcs_client is None:
        try:
            gcs_client = storage.Client(project=settings.google_cloud_project)
        except Exception as exc:
            if DefaultCredentialsError is not None and not isinstance(
                exc, DefaultCredentialsError
            ):
                raise
            raise RuntimeError(
                "Google Cloud Storage is enabled, but Application Default "
                "Credentials were not found. Set USE_CLOUD_STORAGE=false for "
                "local file storage or configure GOOGLE_APPLICATION_CREDENTIALS."
            ) from exc
    return gcs_client


async def save_cloud_upload_file(
    file: UploadFile,
    base_dir: str,
    sub_dir: str | None = None,
    filename_prefix: str | None = None,
) -> tuple[str, bytes]:
    """
    Save an UploadFile to Google Cloud Storage.

    Returns:
        Relative path (blob name) to the saved file, file_bytes
    """
    if not settings.use_cloud_storage:
        return await save_upload_file(file, base_dir, sub_dir, filename_prefix)

    # 1. Read file bytes
    file_bytes = await file.read()

    # 2. Construct the Destination Blob Name
    blob_path_parts = [base_dir]
    if sub_dir:
        blob_path_parts.append(sub_dir)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    extension = Path(file.filename).suffix or ".m4a"
    prefix = filename_prefix or "file"
    filename = f"{prefix}_{timestamp}{extension}"

    blob_path_parts.append(filename)
    destination_blob_name = "/".join(blob_path_parts)

    # 3. Upload to GCS
    bucket = get_gcs_client().bucket(BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)

    # Offload blocking upload to a thread
    def upload():
        blob.upload_from_string(
            file_bytes, content_type=file.content_type or "audio/mp4"
        )

    await asyncio.to_thread(upload)

    # 4. Return relative path and bytes
    # e.g., "brick-audios/ln2rec_20260506_063934.m4a"
    return destination_blob_name, file_bytes


async def save_upload_file(
    file: UploadFile,
    base_dir: str,
    sub_dir: str | None = None,
    filename_prefix: str | None = None,
) -> tuple[str, bytes]:
    """
    Save an UploadFile to disk using pathlib.

    Args:
        file: FastAPI UploadFile
        base_dir: Base directory (e.g. "learner_audio")
        sub_dir: Optional subfolder (e.g. f"user_{learner_id}")
        filename_prefix: Optional prefix (e.g. f"brick_{brick_id}")

    Returns:
        Relative path to the saved file, file_bytes
    """

    # Read file bytes once
    file_bytes = await file.read()

    # Build directory path
    save_dir = Path(base_dir)
    if sub_dir:
        save_dir = save_dir / sub_dir

    # Ensure directory exists
    save_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Get extension safely
    extension = Path(file.filename).suffix or ".m4a"

    prefix = filename_prefix or "file"
    filename = f"{prefix}_{timestamp}{extension}"

    file_path = save_dir / filename

    # Save file
    file_path.write_bytes(file_bytes)

    return str(file_path), file_bytes
