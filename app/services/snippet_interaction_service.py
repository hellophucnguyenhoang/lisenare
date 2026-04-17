from sqlmodel import Session

from app.database import SnippetInteraction
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
        raise ValueError("TIME_SPENT requires duration")

    interaction = SnippetInteraction(
        session_id=session_id,
        snippet_id=snippet_id,
        type=interaction_type,
        duration=duration,
        learner_id=learner_id,
    )

    session.add(interaction)
    session.commit()
    session.refresh(interaction)
    return interaction
