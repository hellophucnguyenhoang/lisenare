from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import PushTokenRegister
from app.services import auth_service, push_token_service

router = APIRouter(prefix="/push-tokens", tags=["Push Tokens"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_push_token(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    data: PushTokenRegister,
) -> Response:
    _, is_created = push_token_service.register_push_token(
        session, data, learner.id
    )

    if is_created:
        return Response(status_code=status.HTTP_201_CREATED)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/send-bulk", status_code=status.HTTP_202_ACCEPTED)
async def send_bulk_notifications(
    session: Annotated[Session, Depends(get_session)],
    # Note: In production, protect this endpoint with an Admin API Key or similar
) -> Response:
    """
    Endpoint to be called by a Scheduler like Cron job.
    It cleans old/broken tokens by checking previous tickets and sends new notifications.
    Only learners with the last successfully sent time is at least 12 hours are sent.
    """
    learner_ids = push_token_service.get_eligible_learner_ids(session)
    if not learner_ids:
        # logger.info("Bulk notifications: No eligible learners to notify at this time.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    push_token_service.send_notifications_to_learners(
        session=session,
        learner_ids=learner_ids,
    )
    # Developer message safely written to system standard output, not leaked to HTTP body
    # logger.info(f"Bulk notifications: Processed notifications for {len(learner_ids)} learners.")
    return Response(status_code=status.HTTP_202_ACCEPTED)
