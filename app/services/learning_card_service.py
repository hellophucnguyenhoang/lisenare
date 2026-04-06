from datetime import datetime, timezone

from fsrs import Card, Scheduler
from sqlmodel import Session, func, select

from app.database import LearningCard

from .spaced_repetition_service import convert_similarity_score_to_fsrs_rating


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

    scheduler = Scheduler()  # use default scheduler
    rating = convert_similarity_score_to_fsrs_rating(score, is_answer_revealed)
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


def get_learning_stats(
    session: Session,
    learner_id: int,
):
    now = datetime.now(timezone.utc)
    total_statement = select(func.count(LearningCard.brick_id)).where(
        LearningCard.learner_id == learner_id
    )
    total_count = session.exec(total_statement).one()
    due_statement = select(func.count(LearningCard.brick_id)).where(
        LearningCard.learner_id == learner_id, LearningCard.due <= now
    )
    due_count = session.exec(due_statement).one()
    return {
        "total_learning": total_count,
        "due_count": due_count,
        "timestamp": now,
    }
