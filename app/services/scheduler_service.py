"""APScheduler setup cho các job định kỳ.

Hiện chạy trong cùng FastAPI process (AsyncIOScheduler). Nếu sau này scale
multi-worker thì chuyển sang Celery Beat hoặc 1 worker chuyên trách.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session

from app.database import engine
from app.services.question_difficulty_service import (
    recompute_all_due_difficulties,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def daily_difficulty_update_job() -> None:
    """Chạy 2h sáng hằng ngày — recompute difficulty cho các câu có response mới."""
    try:
        with Session(engine) as session:
            stats = recompute_all_due_difficulties(session=session)
            logger.info("Daily difficulty update done: %s", stats)
    except Exception:
        logger.exception("Daily difficulty update job failed")


def start_scheduler() -> None:
    if scheduler.running:
        logger.warning("Scheduler already running")
        return
    scheduler.add_job(
        daily_difficulty_update_job,
        CronTrigger(hour=2, minute=0),
        id="daily_difficulty_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started (daily_difficulty_update at 02:00)")


def stop_scheduler() -> None:
    if not scheduler.running:
        return
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
