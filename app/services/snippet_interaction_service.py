from datetime import datetime, timezone

from fastapi import status
from sqlmodel import Session

from app.database import SnippetInteraction, SnippetReaction
from app.exceptions import RequestException
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
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="TIME_SPENT requires duration",
        )

    if interaction_type != InteractionType.TIME_SPENT and duration is not None:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="duration is for TIME_SPENT only",
        )

    if not learner_id and interaction_type in {
        InteractionType.LIKE,
        InteractionType.DISLIKE,
        InteractionType.REMOVE_REACTION,
        InteractionType.ADD,
    }:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{InteractionType.LIKE}, \
                    {InteractionType.DISLIKE}, \
                    {InteractionType.REMOVE_REACTION} \
                    or {InteractionType.ADD} requires an authenticated learner",
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
        existing = session.get(
            SnippetReaction,
            (learner_id, snippet_id),
        )

        match interaction_type:
            case InteractionType.REMOVE_REACTION:
                if existing:
                    session.delete(existing)
            case InteractionType.LIKE | InteractionType.DISLIKE:
                if existing:
                    existing.reaction = interaction_type.value
                    existing.updated_at = datetime.now(timezone.utc)
                else:
                    session.add(
                        SnippetReaction(
                            learner_id=learner_id,
                            snippet_id=snippet_id,
                            reaction=interaction_type.value,
                        )
                    )

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

        embedding = context_search_service.get_embedding(
            session, data.snippet_id
        )
        if embedding is not None:
            print("retrieve embedding not none")
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

    except Exception:
        session.rollback()  # If anything fails, nothing is saved
        raise
