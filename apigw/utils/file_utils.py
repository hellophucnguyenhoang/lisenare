from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

import cloud_storage_client
from constants import ASSETS_DIR


def save_file_bytes(
    content: bytes,
    relative_path: str | Path = "",
    filename_prefix: str = "file",
    extension: str = ".wav",
) -> str:
    """
    Save bytes to disk under ASSETS_DIR.

    Args:
        content: Audio or file bytes
        relative_path: Directory relative to ASSETS_DIR (e.g. "generated-audios")
        filename_prefix: Prefix for the generated filename (default: "file")
        extension: File extension (default: ".wav")

    Returns:
        Path to the saved file relative to ASSETS_DIR
    """
    save_dir = ASSETS_DIR / relative_path if relative_path else ASSETS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if not extension.startswith("."):
        extension = f".{extension}"

    filename = f"{filename_prefix}-{timestamp}{extension}"
    file_path = save_dir / filename
    counter = 1
    while file_path.exists():
        filename = f"{filename_prefix}-{timestamp}_{counter}{extension}"
        file_path = save_dir / filename
        counter += 1

    file_path.write_bytes(content)
    return file_path.relative_to(ASSETS_DIR).as_posix()


async def save_upload_file(
    file: UploadFile,
    relative_path: str | Path = "",
    filename_prefix: str = "file",
) -> tuple[str, bytes]:
    """
    Save an UploadFile to disk under ASSETS_DIR.

    Args:
        file: FastAPI UploadFile
        relative_path: Directory relative to ASSETS_DIR (e.g. "learner-audios/learner-1")
        filename_prefix: Prefix for the generated filename (default: "file")

    Returns:
        Tuple of (path relative to ASSETS_DIR, file_bytes)
    """
    file_bytes = await file.read()
    extension = Path(file.filename).suffix or ".m4a"
    returned_path = save_file_bytes(
        content=file_bytes,
        relative_path=relative_path,
        filename_prefix=filename_prefix,
        extension=extension,
    )
    return returned_path, file_bytes


def _get_content_type(extension: str) -> str:
    ext = extension.lower().lstrip(".")
    mapping = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "ogg": "audio/ogg",
        "webm": "audio/webm",
        "flac": "audio/flac",
    }
    return mapping.get(ext, "application/octet-stream")


def save_file_bytes_to_cloud(
    content: bytes,
    relative_path: str | Path = "",
    filename_prefix: str = "file",
    extension: str = ".wav",
    content_type: str | None = None,
    **kwargs,
) -> str:
    """
    Save bytes directly to cloud storage (S3/Backblaze) under relative_path.

    Args:
        content: Audio or file bytes
        relative_path: Directory/prefix relative to bucket root (e.g. "generated-audios")
        filename_prefix: Prefix for the generated filename (default: "file")
        extension: File extension (default: ".wav")
        content_type: Optional MIME content type (e.g. "audio/wav")

    Returns:
        Relative cloud key / path of the saved file
    """

    dest_dir = kwargs.get("relative_dir", kwargs.get("folder", relative_path))
    dest_str = (
        Path(dest_dir).as_posix()
        if isinstance(dest_dir, Path)
        else str(dest_dir)
    )
    dest_str = dest_str.strip("/")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if not extension.startswith("."):
        extension = f".{extension}"

    filename = f"{filename_prefix}-{timestamp}{extension}"
    s3_key = f"{dest_str}/{filename}" if dest_str else filename

    mime_type = content_type or _get_content_type(extension)
    cloud_storage_client.upload_bytes(
        content=content,
        s3_key=s3_key,
        content_type=mime_type,
    )
    return s3_key


async def save_upload_file_to_cloud(
    file: UploadFile,
    relative_path: str | Path = "",
    filename_prefix: str = "file",
    **kwargs,
) -> tuple[str, bytes]:
    """
    Save an UploadFile directly to cloud storage.

    Args:
        file: FastAPI UploadFile
        relative_path: Directory/prefix relative to bucket root (e.g. "learner-audios/learner-1")
        filename_prefix: Prefix for the generated filename (default: "file")

    Returns:
        Tuple of (relative cloud key, file_bytes)
    """
    dest_dir = kwargs.get("relative_dir", kwargs.get("folder", relative_path))
    file_bytes = await file.read()
    extension = Path(file.filename).suffix or ".m4a"
    content_type = file.content_type or _get_content_type(extension)
    s3_key = save_file_bytes_to_cloud(
        content=file_bytes,
        relative_path=dest_dir,
        filename_prefix=filename_prefix,
        extension=extension,
        content_type=content_type,
    )
    return s3_key, file_bytes
