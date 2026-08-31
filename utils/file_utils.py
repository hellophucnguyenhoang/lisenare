from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile


async def save_upload_file(
    file: UploadFile,
    base_dir: str | None = None,
    sub_dir: str | None = None,
    filename_prefix: str = "file",
) -> tuple[str, bytes]:
    """
    Save an UploadFile to disk using pathlib.

    Args:
        file: FastAPI UploadFile
        base_dir: Base directory (e.g. "learner-audio")
        sub_dir: Optional subfolder (e.g. f"user-{learner_id}")
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

    filename = f"{filename_prefix}_{timestamp}{extension}"
    file_path = save_dir / filename
    file_path.write_bytes(file_bytes)

    return str(file_path), file_bytes
