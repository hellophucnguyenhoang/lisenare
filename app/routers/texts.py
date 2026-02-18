from fastapi import APIRouter, Depends
from schemas.sentence import (
    SentenceCompareRequest, 
    SentenceCompareResponse
)
from sqlmodel import Session
from app.schemas import ReviewCreate
import app.http_client as http_client
from app.services import auth_service, review_service, learning_card_service
from app.database import get_session, Learner

router = APIRouter(prefix="/text", tags=["Text Features"])

@router.post("/comparisons", response_model=SentenceCompareResponse)
async def compare(
    sentence_compare_request: SentenceCompareRequest,
    current_learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session)):
    r = await http_client.client.post(
        "/text/comparisons",
        json=sentence_compare_request.model_dump(mode="json"),
    )
    sentence_compare_response = SentenceCompareResponse.model_validate(r.json())
    if sentence_compare_request.review_base:
        review = ReviewCreate(
            **sentence_compare_request.review_base.model_dump(),
            first_score=sentence_compare_response.score
        )
        review_service.save_review(
            session=session,
            learner_id=current_learner.id,
            review_create=review
        )
        learning_card_service.update_learning_card(
            session=session,
            learner_id=current_learner.id,
            brick_id=sentence_compare_request.review_base.brick_id,
            score=sentence_compare_response.score,
            is_answer_revealed=sentence_compare_request.review_base.is_answer_revealed
        )
    return sentence_compare_response
