from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from cloud_storage_client import download_file
from config import logger, settings
from constants import ASSETS_DIR
from redis_client import get_redis_client
from services import brick_service

ONE_DAY_SECONDS = 86400  # 24 hours in seconds
BRICK_CACHE_PREFIX = "brick_audio:"


_cleanup_scheduler: BackgroundScheduler | None = None


def get_brick_audio_url(
    session: Session,
    brick_id: int,
    learner_id: int,
) -> str:
    """
    Ensure the brick's audio file exists locally at lisenare-assets/<target_audio_path>,
    downloading from cloud storage if needed, and return the full public URL.
    """
    # Verify brick belongs to the authenticated learner
    brick = brick_service.get_brick(session, brick_id, learner_id)

    redis = get_redis_client()
    cache_key = f"{BRICK_CACHE_PREFIX}{brick_id}"
    cached_path: str = redis.get(cache_key)
    if cached_path:
        local_file = ASSETS_DIR / cached_path
        # ensuring the physical file exists
        # and is not just a string path or directory
        if local_file.is_file():
            base_url = settings.asset_base_url.rstrip("/")
            return f"{base_url}/{cached_path.lstrip('/')}"
        else:
            redis.delete(cache_key)
            logger.warning(
                f"Cache hit but file missing from disk: {local_file}. Evicting key."
            )

    # Redis cache miss: read target_audio_path from DB
    target_audio_path = brick.target_audio_path
    local_file = ASSETS_DIR / target_audio_path
    if not local_file.is_file():
        download_file(target_audio_path, local_file)

    # Store in Redis with 1-day TTL
    redis.setex(cache_key, ONE_DAY_SECONDS, target_audio_path)

    # For the cleanup background job
    redis.setex(f"cached_audio:{target_audio_path}", ONE_DAY_SECONDS, "1")

    return f"{settings.asset_base_url}/{target_audio_path}"


def cleanup_expired_audio_files(
    directory: Path | str | None = None,
) -> list[str]:
    """
    Simple background job to delete local audio files that are no longer
    in the Redis cache.
    """
    target_dir = (
        Path(directory)
        if directory is not None
        else (ASSETS_DIR / "system-brick-audios")
    )
    if not target_dir.is_dir():
        return []

    redis = get_redis_client()
    deleted = []

    for file_path in target_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # get the relative path after ASSETS_DIR and force / slashes
        relative_path = file_path.relative_to(ASSETS_DIR).as_posix()
        if not redis.exists(f"cached_audio:{relative_path}"):
            file_path.unlink(missing_ok=True)
            deleted.append(str(file_path))
            logger.info(f"Deleted audio file not in Redis: {file_path}")

    return deleted


def start_audio_cleanup_scheduler(
    interval_hours: int = 1,
) -> BackgroundScheduler:
    """Run cleanup_expired_audio_files on a periodic background schedule."""
    global _cleanup_scheduler
    if _cleanup_scheduler and _cleanup_scheduler.running:
        return _cleanup_scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        cleanup_expired_audio_files,
        "interval",
        hours=interval_hours,
        id="audio_cache_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    _cleanup_scheduler = scheduler
    logger.info(
        f"Started audio cleanup scheduler (interval: {interval_hours}h)"
    )
    return scheduler


def stop_audio_cleanup_scheduler(scheduler: BackgroundScheduler | None = None):
    """Stop the background cleanup scheduler."""
    global _cleanup_scheduler
    active = scheduler or _cleanup_scheduler
    if active and active.running:
        active.shutdown(wait=False)
        logger.info("Stopped audio cleanup scheduler")
    _cleanup_scheduler = None
