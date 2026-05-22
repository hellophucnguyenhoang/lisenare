from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import (
    ExplanationRequest,
    ExplanationResponse,
)
from app.services import (
    auth_service,
    explanation_service,
    learning_card_service,
)

router = APIRouter(prefix="/explanations", tags=["Explanations"])


@router.post("")
def get_explanations(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
    explanation_request: ExplanationRequest,
) -> ExplanationResponse:
    response = explanation_service.generate_vocab_item_for_learner(
        session=session,
        learner_id=learner.id,
        target_term=explanation_request.target_term,
    )
    print(f"simplified responses: {response=}")
    explanation_service.validate_explanation_response(response)
    return response


@router.get(
    "/seen-lemma",
)
def get_seen_lemma(
    session: Annotated[Session, Depends(get_session)],
):
    result = learning_card_service.get_learner_seen_stems(session, 2)
    return result


@router.post(
    "/sentence-familiarity",
)
def get_sentence_familiarity(
    session: Annotated[Session, Depends(get_session)],
    sentence: str = Body(),
) -> float:
    result = learning_card_service.calculate_sentence_familiarity(
        session, 2, sentence
    )
    return result
