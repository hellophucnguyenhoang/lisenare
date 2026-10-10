from datetime import datetime, timezone

from sqlmodel import Session

from config import logger
from database import BrickInteraction, BrickReaction
from schemas import BrickInteractionCreate, InteractionType

from . import session_profile_service
from .context_search_service import search_service


def create_interaction(
    session: Session,
    session_id: str,
    brick_id: int,
    interaction_type: InteractionType,
    learner_id: int,
    commit: bool = True,
) -> BrickInteraction:
    interaction = BrickInteraction(
        session_id=session_id,
        brick_id=brick_id,
        type=interaction_type,
        learner_id=learner_id,
    )
    session.add(interaction)

    existing = session.get(
        BrickReaction,
        (learner_id, brick_id),
    )

    match interaction_type:
        case InteractionType.REMOVE_REACTION:
            if existing:
                session.delete(existing)

        case InteractionType.LIKE:
            if existing:
                existing.reaction = interaction_type.value
                existing.updated_at = datetime.now(timezone.utc)
            else:
                session.add(
                    BrickReaction(
                        learner_id=learner_id,
                        brick_id=brick_id,
                        reaction=interaction_type.value,
                    )
                )

        case _:
            pass

    if commit:
        session.commit()

    return interaction


def handle_interaction_and_update_profile(
    session: Session,
    data: BrickInteractionCreate,
    learner_id: int,
) -> BrickInteraction:
    try:
        interaction = create_interaction(
            session=session,
            session_id=data.session_id,
            brick_id=data.brick_id,
            interaction_type=data.interaction_type,
            learner_id=learner_id,
            commit=True,
        )

        embedding = search_service.get_embedding(session, data.brick_id)

        if embedding is not None:
            session_profile_service.update_session_profile(
                db_session=session,
                session_id=data.session_id,
                new_brick_embedding=embedding,
                interaction_type=data.interaction_type,
                commit=True,
            )
        else:
            logger.warning("embedding None, consider to add brick embeddings")

        return interaction
    except Exception as e:
        session.rollback()
        raise e
