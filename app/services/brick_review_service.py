from collections import defaultdict
from zoneinfo import ZoneInfo

from sqlmodel import Session, case, func, select

from app.database import BrickReview
from app.schemas import ReviewCreate
from utils.db_utils import apply_time_filter

from .spaced_repetition_service import similarity_to_fsrs


def save_review(
    session: Session, learner_id: int, review_create: ReviewCreate
) -> int:
    db_review = BrickReview(
        **review_create.model_dump(),
        learner_id=learner_id,
        fsrs_rating=similarity_to_fsrs(
            review_create.first_score, review_create.is_answer_revealed
        ),
    )
    session.add(db_review)
    session.commit()

    # used for triggering the scheduler optimization task
    statement = select(func.count(BrickReview.id)).where(
        BrickReview.learner_id == learner_id,
        BrickReview.fsrs_log_dict.is_not(None),  # Excludes NULLs
        BrickReview.fsrs_log_dict != {},  # Excludes empty objects
    )
    total_review_count = session.exec(statement).one()
    return total_review_count


def review_exists(session: Session, learner_id: int, brick_id: int) -> bool:
    statement = select(BrickReview).where(
        BrickReview.learner_id == learner_id,
        BrickReview.brick_id == brick_id,
    )
    review = session.exec(statement).first()
    return review is not None


def get_true_retention(
    session: Session, learner_id: int, tz_name: str, days: int | None = None
) -> float:
    """
    The percentage of successfully recalled cards
    """
    statement = select(
        func.count().label("total_reviews"),
        func.count(case((BrickReview.fsrs_rating > 1, 1))).label(
            "successful_reviews"
        ),
    ).where(BrickReview.learner_id == learner_id)

    statement = apply_time_filter(
        statement, BrickReview.reviewed_at, tz_name, days
    )

    result = session.exec(statement).one()
    if result.total_reviews == 0:
        return 0.0

    return round(result.successful_reviews / result.total_reviews, 2)


def to_timeseries(rows):
    """
    Convert [(date, count)] → [{"date": ..., "value": count}]
    """
    return [
        {
            "date": day,
            "value": count,
        }
        for day, count in rows
    ]


def get_daily_review_counts(
    session: Session,
    learner_id: int,
    tz_name: str,
    days: int | None = None,
):
    """
    Count number of reviews per local calendar day.
    """

    # 1. Fetch raw timestamps (UTC)
    statement = select(BrickReview.reviewed_at).where(
        BrickReview.learner_id == learner_id
    )

    statement = apply_time_filter(
        statement, BrickReview.reviewed_at, tz_name, days
    )

    rows = session.exec(statement).all()

    # 2. Convert to local day + group
    tz = ZoneInfo(tz_name)
    counts = defaultdict(int)

    for reviewed_at in rows:
        local_day = reviewed_at.astimezone(tz).date()
        counts[local_day] += 1

    # 3. Sort
    return sorted(counts.items())  # [(date, count)]
