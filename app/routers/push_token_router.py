from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import PushTokenRegister, StatusResponse, StatusResponseType
from app.services import auth_service, push_token_service

router = APIRouter(prefix="/push-tokens", tags=["Push Tokens"])


@router.post("")
async def register_push_token(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    data: PushTokenRegister,
) -> StatusResponse:
    db_token = push_token_service.register_push_token(
        session, data, learner.id
    )
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message=f"Push token id: {db_token.id}",
    )


@router.post("/send-bulk")
async def send_bulk_notifications(
    session: Annotated[Session, Depends(get_session)],
    # Note: In production, protect this endpoint with an Admin API Key or similar
):
    """
    Endpoint to be called by a Scheduler like Cron job.
    It cleans old/broken tokens by checking previous tickets and sends new notifications.
    Only learners with the last successfully sent time is at least 12 hours are sent.
    """
    learner_ids = push_token_service.get_eligible_learner_ids(session)
    if not learner_ids:
        return StatusResponse(
            status=StatusResponseType.SUCCESS,
            message="No eligible learners to notify at this time.",
        )

    push_token_service.send_notifications_to_learners(
        session=session,
        learner_ids=learner_ids,
    )

    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message=f"Processed notifications for {len(learner_ids)} learners.",
    )
