from collections import defaultdict
from zoneinfo import ZoneInfo

from fsrs import Card
from sqlmodel import Session, case, func, select

from app.database import BrickMemory, BrickReview
from app.schemas import ReviewCreate
from utils.db_utils import apply_time_filter

from .spaced_repetition_service import (
    get_scheduler_for_learner,
    similarity_to_fsrs,
)


def save_review(
    session: Session, learner_id: int, review_create: ReviewCreate
) -> int:
    fsrs_rating = similarity_to_fsrs(
        review_create.first_score, review_create.is_answer_revealed
    )

    # 1. Fetch or initialize learning card
    statement = select(BrickMemory).where(
        BrickMemory.learner_id == learner_id,
        BrickMemory.brick_id == review_create.brick_id,
    )
    db_learning_card = session.exec(statement).first()
    if db_learning_card is None:
        card = Card()
    else:
        card = Card.from_dict(db_learning_card.fsrs_card_dict)

    # 2. Review card using learner's scheduler
    scheduler = get_scheduler_for_learner(session, learner_id)
    card, review_log = scheduler.review_card(card, fsrs_rating)

    # 3. Create review with fsrs log
    db_review = BrickReview(
        **review_create.model_dump(),
        learner_id=learner_id,
        fsrs_rating=fsrs_rating,
        fsrs_log_dict=review_log.to_dict(),
    )
    session.add(db_review)

    # 4. Update or create BrickMemory
    if db_learning_card is None:
        db_learning_card = BrickMemory(
            learner_id=learner_id,
            brick_id=review_create.brick_id,
        )

    db_learning_card.fsrs_card_dict = card.to_dict()
    db_learning_card.due = card.due
    session.add(db_learning_card)
    session.commit()

    # 5. Count total reviews for background optimization
    statement = select(func.count(BrickReview.id)).where(
        BrickReview.learner_id == learner_id,
        BrickReview.fsrs_log_dict.is_not(None),
        BrickReview.fsrs_log_dict != {},
    )
    total_learner_reviews = session.exec(statement).one()
    return total_learner_reviews


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
