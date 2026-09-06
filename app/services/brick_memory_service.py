import math
import random
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import status
from fsrs import Card, Optimizer, ReviewLog, Scheduler
from sqlalchemy import Float, cast
from sqlmodel import Session, case, func, select

from app.database import (
    Brick,
    BrickMemory,
    BrickReview,
    LearnerSetting,
    engine,
)
from app.exceptions import RequestException
from app.schemas import TimeSeriesPoint
from utils.db_utils import apply_time_filter
from utils.text_utils import calculate_rarity, get_lenient_stems

from .brick_review_service import (
    get_daily_review_counts,
    get_true_retention,
    to_timeseries,
)
from .spaced_repetition_service import get_scheduler_for_learner


def optimize_learner_scheduler(learner_id: int):
    print(f"Start optimizing scheduler for the learner {learner_id}")
    with Session(engine) as session:
        # 1. Load all reviews to train the optimizer
        statement = select(BrickReview).where(
            BrickReview.learner_id == learner_id
        )
        reviews = session.exec(statement).all()

        fsrs_logs = [
            ReviewLog.from_dict(r.fsrs_log_dict)
            for r in reviews
            if r.fsrs_log_dict
        ]
        log_count = len(fsrs_logs)
        print(f"Found {log_count} valid FSRS logs")

        if log_count < 100:
            print(
                f"Optimization aborted: Not enough logs ({len(fsrs_logs)} < 100)"
            )
            return

        # 2. Run Optimizer
        try:
            optimizer = Optimizer(fsrs_logs)
            # Weights can usually be computed with ~100+ logs
            optimal_params = optimizer.compute_optimal_parameters()
            print(f"Done computing optimal params for {learner_id = }")

            # Retention requires 512. Check count before calling.
            optimal_retention = 0.9  # Default
            if log_count >= 512:
                try:
                    optimal_retention = optimizer.compute_optimal_retention(
                        optimal_params
                    )
                    print(
                        f"Done computing optimal retention for {learner_id = }"
                    )
                except ValueError as e:
                    print(f"Retention optimization failed, using 0.9: {e}")
            else:
                print(
                    f"Skipping retention optimization for learner {learner_id} (Need 512, have {log_count})"
                )

            # 3. Save Settings
            settings = session.get(
                LearnerSetting, learner_id
            ) or LearnerSetting(learner_id=learner_id)
            settings.fsrs_weights = optimal_params
            settings.target_retention = optimal_retention
            session.add(settings)

            # 4. Reschedule all cards for this learner
            optimal_scheduler = Scheduler(optimal_params, optimal_retention)

            # Fetch all learning cards for this user
            card_statement = select(BrickMemory).where(
                BrickMemory.learner_id == learner_id
            )
            learning_cards = session.exec(card_statement).all()

            for db_card in learning_cards:
                # Filter logs specific to THIS card (brick)
                card_logs = [
                    ReviewLog.from_dict(r.fsrs_log_dict)
                    for r in reviews
                    if r.brick_id == db_card.brick_id and r.fsrs_log_dict
                ]

                if not card_logs:
                    continue

                # Re-initialize a fresh card and replay the history with the new weights
                # Note: reschedule_card typically needs the card and its specific log history
                fresh_card = Card()
                # Use the card_id from the first log entry for this card
                fresh_card.card_id = card_logs[0].card_id
                rescheduled_card = optimal_scheduler.reschedule_card(
                    fresh_card, card_logs
                )

                # Update the database card with new stability/difficulty/due date
                db_card.fsrs_card_dict = rescheduled_card.to_dict()
                db_card.due = rescheduled_card.due
                session.add(db_card)

            session.commit()
            print(f"Successfully optimized for learner {learner_id}")

        except Exception as e:
            print(f"Optimization failed for learner {learner_id}: {e}")
            traceback.print_exc()


def get_average_stability(
    session: Session, learner_id: int, tz_name: str, days: int | None = None
) -> float:
    stability_as_text = BrickMemory.fsrs_card_dict["stability"].astext

    # Reviews within the requested time range
    review_subquery = (
        select(BrickReview.brick_id)
        .where(BrickReview.learner_id == learner_id)
        .distinct()
    )

    review_subquery = apply_time_filter(
        review_subquery,
        BrickReview.reviewed_at,
        tz_name,
        days,
    ).subquery()

    # Average stability of cards that were reviewed
    statement = (
        select(func.avg(cast(stability_as_text, Float)))
        .where(BrickMemory.learner_id == learner_id)
        .where(BrickMemory.brick_id.in_(select(review_subquery.c.brick_id)))
    )

    result = session.exec(statement).one()

    return round(result, 2) if result is not None else 0.0


def get_total_memorized(
    session: Session, learner_id: int, tz_name: str, days: int | None = None
) -> float:
    statement = select(BrickMemory.fsrs_card_dict).where(
        BrickMemory.learner_id == learner_id
    )

    statement = apply_time_filter(
        statement, BrickMemory.created_at, tz_name, days
    )

    rows = session.exec(statement).all()
    total = 0.0

    scheduler = get_scheduler_for_learner(session, learner_id)
    for fsrs_card_dict in rows:
        card = Card.from_dict(fsrs_card_dict)
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
        func.count(case((BrickMemory.due <= now, 1))).label("due_count"),
    ).where(BrickMemory.learner_id == learner_id)

    statement = apply_time_filter(
        statement, BrickMemory.created_at, tz_name, days
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

    # Fetch raw timestamps (UTC)
    statement = select(BrickMemory.created_at).where(
        BrickMemory.learner_id == learner_id
    )

    statement = apply_time_filter(
        statement, BrickMemory.created_at, tz_name, days
    )

    rows = session.exec(statement).all()

    # Convert to local day + group
    tz = ZoneInfo(tz_name)
    counts = defaultdict(int)

    for created_at in rows:
        local_day = created_at.astimezone(tz).date()
        counts[local_day] += 1

    # Sort by day
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
            "data": to_cumulative(rows),
        }

    elif metric == "reviews":
        rows = get_daily_review_counts(session, learner_id, tz_name, days)
        return {
            "metric": "reviews",
            "unit": "reviews",
            "data": to_timeseries(rows),  # NOT cumulative
        }

    else:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=f"Unsupported metric: {metric}",
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


def fill_missing_days(
    points: list[TimeSeriesPoint],
    days: int | None = None,
    fill_strategy: Literal["zero", "carry"] = "zero",
) -> list[TimeSeriesPoint]:
    """
    Fill missing dates in a timeseries.

    Strategies:
    - zero:
        missing days become 0

    - carry:
        missing days reuse previous value
        useful for cumulative metrics
    """

    if not points:
        return []

    # Ensure sorted
    points = sorted(points, key=lambda p: p.date)

    point_map = {p.date: p.value for p in points}

    start_date = points[0].date
    end_date = points[-1].date

    filled: list[TimeSeriesPoint] = []

    current = start_date
    previous_value = 0.0

    while current <= end_date:
        if current in point_map:
            value = point_map[current]
            previous_value = value
        else:
            if fill_strategy == "zero":
                value = 0.0
            elif fill_strategy == "carry":
                value = previous_value
            else:
                raise ValueError(f"Unsupported fill strategy: {fill_strategy}")

        filled.append(
            TimeSeriesPoint(
                date=current,
                value=value,
            )
        )

        current += timedelta(days=1)

    return filled


def downsample_points(data: list[TimeSeriesPoint], max_points: int = 40):
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


def get_learner_seen_stems(
    session: Session,
    learner_id: int,
) -> set[str]:
    """
    Get all unique stems the learner has seen.
    """

    statement = (
        select(Brick.target_text)
        .join(BrickMemory, BrickMemory.brick_id == Brick.id)
        .where(BrickMemory.learner_id == learner_id)
    )

    sentences = session.exec(statement).all()

    seen_stems = set()

    for sentence in sentences:
        seen_stems.update(get_lenient_stems(sentence))

    return seen_stems


def calculate_sentence_familiarity(
    session: Session,
    learner_id: int,
    sentence: str,
) -> float:
    """
    Calculate how familiar/easy a sentence is for a learner.

    Score range:
        [0, 1]

    Higher means:
        - fewer unknown words
        - unknown words are more common
    """

    sentence_stems = get_lenient_stems(sentence)

    if not sentence_stems:
        return 0.0

    learner_seen_stems = get_learner_seen_stems(
        session=session,
        learner_id=learner_id,
    )

    unknown_stems = sentence_stems - learner_seen_stems

    unknown_ratio = len(unknown_stems) / len(sentence_stems)
    print(f"{unknown_ratio=}")
    # No unknown words -> perfectly familiar
    if not unknown_stems:
        return 1.0

    avg_unknown_rarity = sum(
        calculate_rarity(word) for word in unknown_stems
    ) / len(unknown_stems)
    print(f"{avg_unknown_rarity=}")

    familiarity = math.exp(-unknown_ratio - avg_unknown_rarity)
    print(f"{familiarity=}|{sentence=}")
    print()
    return familiarity
