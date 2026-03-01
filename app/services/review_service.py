from sqlmodel import Session

from app.schemas import ReviewCreate
from app.database import Review
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
