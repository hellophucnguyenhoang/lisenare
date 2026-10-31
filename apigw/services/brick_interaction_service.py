from sqlmodel import Session

from config import logger
from database import BrickInteraction
from schemas import BrickInteractionCreate, InteractionType

from . import search_service, session_profile_service


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

    if commit:
        session.commit()

    logger.info(
        f"Recorded interaction '{interaction_type.value}' for brick ID: {brick_id}, "
        f"learner ID: {learner_id}, session ID: {session_id}"
    )
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
            logger.warning(
                f"Missing embedding for brick ID: {data.brick_id}, skipped profile update"
            )

        return interaction
    except Exception as e:
        session.rollback()
        logger.error(
            f"Failed to process interaction for brick ID: {data.brick_id}, "
            f"learner ID: {learner_id}, session ID: {data.session_id}: {e}",
            exc_info=True,
        )
        raise e
