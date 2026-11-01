from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import status
from sqlmodel import Session

from cloud_storage_client import download_file
from config import logger, settings
from constants import (
    ASSETS_DIR,
    BRICK_IMAGE_CACHE_PREFIX,
    BRICK_IMAGES_DIR,
    IMAGE_CACHE_TTL_SECONDS,
    IMAGE_CATCH_PREFIX,
)
from database import Brick
from exceptions import RequestException
from redis_client import get_redis_client

_cleanup_scheduler: BackgroundScheduler | None = None


def get_brick_image_url(
    session: Session,
    brick_id: int,
    learner_id: int,
) -> str:
    """
    Ensure the brick's image file exists locally at lisenare-assets/<image_path>,
    downloading from cloud storage if needed, and return the full public URL.
    """
    brick = session.get(Brick, brick_id)
    if not brick or (brick.is_private and brick.creator_id != learner_id):
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick {brick_id} not found",
        )

    if not brick.image_path:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Brick {brick_id} has no image",
        )

    redis = get_redis_client()
    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick_id}"
    cached_path: str = redis.get(cache_key)
    if cached_path:
        local_file = ASSETS_DIR / cached_path
        if local_file.is_file():
            redis.expire(cache_key, IMAGE_CACHE_TTL_SECONDS)
            redis.expire(
                f"{IMAGE_CATCH_PREFIX}{cached_path}", IMAGE_CACHE_TTL_SECONDS
            )

            base_url = settings.asset_base_url.rstrip("/")
            return f"{base_url}/{cached_path.lstrip('/')}"
        else:
            redis.delete(cache_key)
            logger.warning(
                f"Cache hit but image missing from disk: {local_file}. Evicting key."
            )

    # Redis cache miss: read image_path from DB
    image_path = brick.image_path
    local_file = ASSETS_DIR / image_path

    if not local_file.is_file():
        download_file(image_path, local_file)

    # Store in Redis with 1-day TTL
    redis.setex(cache_key, IMAGE_CACHE_TTL_SECONDS, image_path)

    # For the cleanup background job
    redis.setex(
        f"{IMAGE_CATCH_PREFIX}{image_path}",
        IMAGE_CACHE_TTL_SECONDS,
        "1",
    )

    base_url = settings.asset_base_url.rstrip("/")
    return f"{base_url}/{image_path.lstrip('/')}"


def clear_brick_image_cache(brick_id: int) -> None:
    """Clear the cached image entry for a brick from Redis."""
    redis = get_redis_client()
    redis.delete(f"{BRICK_IMAGE_CACHE_PREFIX}{brick_id}")


def cleanup_expired_image_files(
    directory: Path | str | None = None,
) -> list[str]:
    """
    Background job to delete local brick image files that are no longer
    in the Redis cache.
    """
    target_dir = (
        Path(directory)
        if directory is not None
        else (ASSETS_DIR / BRICK_IMAGES_DIR)
    )
    if not target_dir.is_dir():
        return []

    redis = get_redis_client()
    deleted = []

    for file_path in target_dir.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in [
            ".webp",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
        ]:
            continue

        try:
            relative_path = file_path.relative_to(ASSETS_DIR).as_posix()
        except ValueError:
            if directory is not None:
                relative_path = file_path.relative_to(
                    Path(directory)
                ).as_posix()
            else:
                continue

        # Ensure we only clean brick-images and never touch avatars or other asset directories
        if not (
            relative_path.startswith(f"{BRICK_IMAGES_DIR.name}/")
            or relative_path.startswith(f"{BRICK_IMAGES_DIR}/")
        ):
            continue

        if not redis.exists(f"{IMAGE_CATCH_PREFIX}{relative_path}"):
            file_path.unlink(missing_ok=True)
            deleted.append(str(file_path))
            logger.info(f"Deleted image file not in Redis: {file_path}")

    return deleted


def start_image_cleanup_scheduler(
    interval_hours: int = 1,
) -> BackgroundScheduler:
    """Run cleanup_expired_image_files on a periodic background schedule."""
    global _cleanup_scheduler
    if _cleanup_scheduler and _cleanup_scheduler.running:
        return _cleanup_scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        cleanup_expired_image_files,
        "interval",
        hours=interval_hours,
        id="image_cache_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    _cleanup_scheduler = scheduler
    logger.info(
        f"Started image cleanup scheduler (interval: {interval_hours}h)"
    )
    return scheduler


def stop_image_cleanup_scheduler(scheduler: BackgroundScheduler | None = None):
    """Stop the background cleanup scheduler."""
    global _cleanup_scheduler
    active = scheduler or _cleanup_scheduler
    if active and active.running:
        active.shutdown(wait=False)
        logger.info("Stopped image cleanup scheduler")
    _cleanup_scheduler = None
