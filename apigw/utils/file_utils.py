from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile, status
from PIL import Image, ImageOps, ImageSequence

import cloud_storage_client
from config import logger
from constants import (
    ANIMATED_IMAGE_MAX_SIZE,
    ASSETS_DIR,
    STATIC_IMAGE_MAX_SIZE,
    WEBP_METHOD,
    WEBP_QUALITY,
)
from exceptions import RequestException


def compress_image(data: bytes) -> bytes:
    """Convert an image to optimized WebP."""
    with Image.open(BytesIO(data)) as image:
        is_animated = getattr(image, "is_animated", False)

        if is_animated:
            frames = []
            durations = []

            for frame in ImageSequence.Iterator(image):
                frame = frame.convert("RGBA")
                frame.thumbnail(
                    (ANIMATED_IMAGE_MAX_SIZE, ANIMATED_IMAGE_MAX_SIZE),
                    Image.Resampling.LANCZOS,
                )

                frames.append(frame.copy())
                durations.append(frame.info.get("duration", 100))

            output = BytesIO()

            frames[0].save(
                output,
                format="WEBP",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                quality=WEBP_QUALITY,
                method=WEBP_METHOD,
            )

        else:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (STATIC_IMAGE_MAX_SIZE, STATIC_IMAGE_MAX_SIZE),
                Image.Resampling.LANCZOS,
            )

            if image.mode not in ("RGB", "RGBA"):
                image = image.convert(
                    "RGBA" if "transparency" in image.info else "RGB"
                )

            output = BytesIO()

            image.save(
                output,
                format="WEBP",
                quality=WEBP_QUALITY,
                method=WEBP_METHOD,
            )

        return output.getvalue()


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
        "webp": "image/webp",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
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


async def process_and_save_image(
    file: UploadFile,
    relative_path: str | Path = "",
    filename_prefix: str = "image",
) -> str:
    """
    Validate, compress to WebP, and save an uploaded image file to cloud storage.

    Args:
        file: FastAPI UploadFile containing image bytes.
        relative_path: Directory/prefix relative to bucket root / cloud storage.
        filename_prefix: Prefix for the generated file name (default: "image").

    Returns:
        The relative cloud key / path of the saved WebP image.
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Uploaded image file is empty",
        )

    try:
        compressed_bytes = compress_image(raw_bytes)
    except Exception as e:
        logger.warning(f"Failed to compress image: {e}")
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Invalid image file format",
        ) from e

    return save_file_bytes_to_cloud(
        content=compressed_bytes,
        relative_path=relative_path,
        filename_prefix=filename_prefix,
        extension=".webp",
        content_type="image/webp",
    )
