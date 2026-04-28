import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from fsrs import Card, Scheduler
from sqlmodel import Session, case, func, select

from app.database import LearningCard
from utils.db_utils import apply_time_filter

from .review_service import (
    get_daily_review_counts,
    get_true_retention,
    to_timeseries,
)
from .spaced_repetition_service import similarity_to_fsrs

scheduler = Scheduler()  # use default scheduler


def update_learning_card(
    session: Session,
    learner_id: int,
    brick_id: int,
    score: float,
    is_answer_revealed: bool,
):
    statement = select(LearningCard).where(
        LearningCard.learner_id == learner_id,
        LearningCard.brick_id == brick_id,
    )
    db_learning_card = session.exec(statement).first()
    # first time review
    if db_learning_card is None:
        card = Card()
    # existing card
    else:
        card = Card.from_json(db_learning_card.fsrs_card_json)

    rating = similarity_to_fsrs(score, is_answer_revealed)
    card, review_log = scheduler.review_card(card, rating)

    # create if needed
    if db_learning_card is None:
        db_learning_card = LearningCard(
            learner_id=learner_id,
            brick_id=brick_id,
        )

    db_learning_card.fsrs_card_json = card.to_json()
    db_learning_card.due = card.due
    session.add(db_learning_card)
    session.commit()


def get_average_stability(
    session: Session, learner_id: int, tz_name: str, days: int | None = None
) -> float:
    statement = select(
        func.avg(func.json_extract(LearningCard.fsrs_card_json, "$.stability"))
    ).where(LearningCard.learner_id == learner_id)

    statement = apply_time_filter(
        statement, LearningCard.created_at, tz_name, days
    )

    result = session.exec(statement).one()
    return round(result, 2) if result is not None else 0.0


def get_total_memorized(
    session: Session, learner_id: int, tz_name: str, days: int | None = None
) -> float:
    statement = select(LearningCard.fsrs_card_json).where(
        LearningCard.learner_id == learner_id
    )

    statement = apply_time_filter(
        statement, LearningCard.created_at, tz_name, days
    )

    rows = session.exec(statement).all()
    total = 0.0

    for fsrs_card_json in rows:
        card = Card.from_json(fsrs_card_json)
        retrievability = scheduler.get_card_retrievability(card)
        if retrievability is not None:
            total += retrievability

    return round(total, 2)


def get_learning_stats(
    session: Session,
    learner_id: int,
    tz_name: str,
    days: int | None = None,
):
    now = datetime.now(timezone.utc)
    statement = select(
        func.count().label("total_learning"),
        func.count(case((LearningCard.due <= now, 1))).label("due_count"),
    ).where(LearningCard.learner_id == learner_id)

    statement = apply_time_filter(
        statement, LearningCard.created_at, tz_name, days
    )

    result = session.exec(statement).one()
    return {
        "total_learning": result.total_learning,
        "due_count": result.due_count,
        "true_retention": get_true_retention(
            session, learner_id, tz_name, days
        ),
        "average_stability": get_average_stability(
            session, learner_id, tz_name, days
        ),
        "total_memorized": get_total_memorized(
            session, learner_id, tz_name, days
        ),
        "timestamp": now,
    }


def to_cumulative(rows):
    """
    Convert daily counts into cumulative totals.

    Input:  [(date, count), ...]
    Output: [{"date": ..., "value": cumulative_sum}, ...]
    """
    result = []
    total = 0

    for day, count in rows:
        total += count
        result.append({"date": day, "value": total})

    return result


def get_daily_learning_counts(
    session: Session,
    learner_id: int,
    tz_name: str,
    days: int | None = None,
):
    """
    Get number of cards created per local calendar day.

    - Time filtering is applied in UTC (via apply_time_filter)
    - Grouping is done in Python to ensure correct timezone handling
    """

    # 1. Fetch raw timestamps (UTC)
    statement = select(LearningCard.created_at).where(
        LearningCard.learner_id == learner_id
    )

    statement = apply_time_filter(
        statement, LearningCard.created_at, tz_name, days
    )

    rows = session.exec(statement).all()

    # 2. Convert to local day + group
    tz = ZoneInfo(tz_name)
    counts = defaultdict(int)

    for created_at in rows:
        local_day = created_at.astimezone(tz).date()
        counts[local_day] += 1

    # 3. Sort by day
    return sorted(counts.items())  # [(date, count)]


def get_learning_timeseries(
    session: Session,
    learner_id: int,
    tz_name: str,
    days: int | None = None,
    metric: str = "total_learning",
):
    """
    Return timeseries data depending on metric.
    """

    if metric == "total_learning":
        rows = get_daily_learning_counts(session, learner_id, tz_name, days)
        return {
            "metric": "total_learning",
            "unit": "cards",
            "data": to_cumulative(rows),  # cumulative
        }

    elif metric == "reviews":
        rows = get_daily_review_counts(session, learner_id, tz_name, days)
        return {
            "metric": "reviews",
            "unit": "reviews",
            "data": to_timeseries(rows),  # NOT cumulative
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported metric: {metric}",
        )


def get_learning_timeseries_mock(
    session,
    learner_id: int,
    tz_name: str,
    days: int | None,
    metric: str,
):
    """
    Fake data generator for chart testing.

    - total_learning: cumulative growth
    - reviews: random daily values
    """

    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    # default range
    if days is None:
        days = 50  # fallback for "all"

    # generate list of dates (old → new)
    dates = [today - timedelta(days=i) for i in reversed(range(days))]

    data = []

    if metric == "total_learning":
        total = 0
        for d in dates:
            daily = random.randint(1, 5)  # fake daily learning
            total += daily

            data.append(
                {
                    "date": d,
                    "value": total,
                }
            )

    elif metric == "reviews":
        for d in dates:
            data.append(
                {
                    "date": d,
                    "value": random.randint(0, 20),
                }
            )

    else:
        # fallback
        for d in dates:
            data.append(
                {
                    "date": d,
                    "value": 0,
                }
            )

    return {
        "metric": metric,
        "unit": "cards" if metric == "total_learning" else "reviews",
        "data": data,
    }


def downsample_points(data: list[dict], max_points: int = 50):
    """
    Reduce number of points while keeping overall shape.
    """
    n = len(data)

    if n <= max_points:
        return data

    step = n / max_points

    result = []
    for i in range(max_points):
        idx = int(i * step)
        result.append(data[idx])

    # always ensure last point is included
    if result[-1] != data[-1]:
        result[-1] = data[-1]

    return result
