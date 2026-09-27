from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

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
