from fastapi import HTTPException, status
from sqlmodel import Session

from app.database import SnippetInteraction, SnippetLike
from app.schemas import InteractionType


def create_interaction(
    session: Session,
    session_id: str,
    snippet_id: int,
    interaction_type: InteractionType,
    duration: float | None = None,
    learner_id: int | None = None,
) -> SnippetInteraction:

    if interaction_type == InteractionType.TIME_SPENT and duration is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TIME_SPENT requires duration",
        )

    if not learner_id and interaction_type in {
        InteractionType.LIKE,
        InteractionType.UNLIKE,
        InteractionType.ADD,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LIKE, UNLIKE, or ADD requires learner_id",
        )

    interaction = SnippetInteraction(
        session_id=session_id,
        snippet_id=snippet_id,
        type=interaction_type,
        duration=duration,
        learner_id=learner_id,
    )
    session.add(interaction)

    if learner_id:
        if interaction_type == InteractionType.LIKE:
            existing = session.get(
                SnippetLike,
                (learner_id, snippet_id),
            )
            if not existing:
                session.add(
                    SnippetLike(
                        learner_id=learner_id,
                        snippet_id=snippet_id,
                    )
                )

        elif interaction_type == InteractionType.UNLIKE:
            existing = session.get(
                SnippetLike,
                (learner_id, snippet_id),
            )
            if existing:
                session.delete(existing)

    session.commit()
    session.refresh(interaction)
    return interaction
