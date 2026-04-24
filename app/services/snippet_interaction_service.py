from fastapi import HTTPException, status
from sqlmodel import Session

from app.database import SnippetInteraction, SnippetLike
from app.schemas import InteractionType, SnippetInteractionCreate
from app.services import session_profile_service
from app.services.context_search_service import context_search_service


def create_interaction(
    session: Session,
    session_id: str,
    snippet_id: int,
    interaction_type: InteractionType,
    duration: float | None = None,
    learner_id: int | None = None,
    commit: bool = True,
) -> SnippetInteraction:

    if interaction_type == InteractionType.TIME_SPENT and duration is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TIME_SPENT requires duration",
        )

    if interaction_type != InteractionType.TIME_SPENT and duration is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="duration is for TIME_SPENT",
        )

    if not learner_id and interaction_type in {
        InteractionType.LIKE,
        InteractionType.UNLIKE,
        InteractionType.ADD,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LISTEN, LIKE, UNLIKE, or ADD requires learner_id",
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

    if commit:
        session.commit()
        session.refresh(interaction)

    return interaction


def handle_interaction_and_update_profile(
    session: Session,
    data: SnippetInteractionCreate,
    learner_id: int | None,
) -> SnippetInteraction:
    try:
        interaction = create_interaction(
            session=session,
            session_id=data.session_id,
            snippet_id=data.snippet_id,
            interaction_type=data.interaction_type,
            duration=data.duration,
            learner_id=learner_id,
            commit=False,
        )

        embedding = context_search_service.get_embedding(data.snippet_id)
        if embedding is not None:
            session_profile_service.update_session_profile(
                db_session=session,
                session_id=data.session_id,
                new_snippet_embedding=embedding,
                interaction_type=data.interaction_type,
                duration=data.duration,
                commit=False,
            )

        # Commit everything together
        session.commit()
        return interaction

    except Exception as e:
        session.rollback()  # If anything fails, nothing is saved
        raise e
