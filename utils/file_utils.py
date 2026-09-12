from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile


def save_file_bytes(
    content: bytes,
    base_dir: str | None = None,
    sub_dir: str | None = None,
    filename_prefix: str = "file",
    extension: str = ".wav",
) -> str:
    """
    Save bytes to disk using pathlib.

    Args:
        content: Audio or file bytes
        base_dir: Base directory (e.g. "lisenare-assets/brick-audios")
        sub_dir: Optional subfolder (e.g. f"learner-{learner_id}")
        filename_prefix: Optional prefix (e.g. "tts")
        extension: File extension (default: ".wav")

    Returns:
        Relative path to the saved file after the lisenare-assets/ folder
    """
    save_dir = Path(base_dir) if base_dir else Path(".")
    if sub_dir:
        save_dir = save_dir / sub_dir

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

    path_str = file_path.as_posix()
    if "lisenare-assets/" in path_str:
        return path_str.split("lisenare-assets/", 1)[1]
    return path_str


save_bytes_file = save_file_bytes


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
        base_dir: Base directory (e.g. "lisenare-assets/learner-audio")
        sub_dir: Optional subfolder (e.g. f"learner-{learner_id}")
        filename_prefix: Optional prefix (e.g. f"brick-{brick_id}")

    Returns:
        Relative path to the saved file after the lisenare-assets/ folder, file_bytes
    """
    file_bytes = await file.read()
    extension = Path(file.filename).suffix or ".m4a"
    returned_path = save_file_bytes(
        content=file_bytes,
        base_dir=base_dir,
        sub_dir=sub_dir,
        filename_prefix=filename_prefix,
        extension=extension,
    )
    return returned_path, file_bytes
