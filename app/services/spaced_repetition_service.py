from fsrs import Rating, Scheduler
from sqlmodel import Session

from app.database import LearnerSetting


def get_scheduler_for_learner(session: Session, learner_id: int) -> Scheduler:
    """
    Loads a personalized FSRS scheduler for a specific learner.
    Falls back to a default scheduler if no settings exist.
    """
    settings = session.get(LearnerSetting, learner_id)
    if settings and settings.fsrs_weights:
        return Scheduler(
            settings.fsrs_weights,
            settings.target_retention,
        )
    return Scheduler()


def similarity_to_fsrs(
    first_review_score: float, is_answer_revealed: bool
) -> Rating:
    if is_answer_revealed:
        return Rating.Again
    if first_review_score < 0.45:
        return Rating.Again
    elif first_review_score < 0.65:
        return Rating.Hard
    elif first_review_score < 0.85:
        return Rating.Good
    else:
        return Rating.Easy
