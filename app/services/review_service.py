from sqlmodel import Session, select

from app.database import Review
from app.schemas import ReviewCreate

from .spaced_repetition_service import convert_similarity_score_to_fsrs_rating


def save_review(
    session: Session, learner_id: int, review_create: ReviewCreate
) -> None:
    db_review = Review(
        **review_create.model_dump(),
        learner_id=learner_id,
        fsrs_rating=convert_similarity_score_to_fsrs_rating(
            review_create.first_score, review_create.is_answer_revealed
        ),
    )
    session.add(db_review)
    session.commit()


def review_exists(session: Session, learner_id: int, brick_id: int) -> bool:
    statement = select(Review).where(
        Review.learner_id == learner_id,
        Review.brick_id == brick_id,
    )

    review = session.exec(statement).first()
    return review is not None
