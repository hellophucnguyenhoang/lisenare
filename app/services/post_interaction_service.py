import json
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.database import PostInteraction
from app.services import bandit_service


def create_or_update_interaction(
    session: Session,
    learner_id: int,
    post_id: int,
    arm_feature: str | None = None,
    reward: float | None = None,
) -> PostInteraction:
    # Check if interaction already exists (since they are primary keys)
    statement = select(PostInteraction).where(
        PostInteraction.learner_id == learner_id,
        PostInteraction.post_id == post_id,
    )
    interaction = session.exec(statement).first()

    if not interaction:
        # Create new record
        interaction = PostInteraction(
            learner_id=learner_id,
            post_id=post_id,
            arm_feature=arm_feature,
            reward=reward,
        )
    else:
        # Update existing
        interaction.reward = reward
        interaction.created_at = datetime.now(timezone.utc)

        # Only update model if we have the features saved from the recommendation step
        if interaction.arm_feature and reward is not None:
            bandit_service.update_model(reward, interaction.arm_feature)

    session.add(interaction)
    session.commit()
    session.refresh(interaction)
    return interaction


def get_learner_history(
    session: Session, learner_id: int, history_limit: int = 50
):
    statement = (
        select(PostInteraction.post_id, PostInteraction.reward)
        .where(
            PostInteraction.learner_id == learner_id,
            PostInteraction.reward.is_not(None),
        )
        .order_by(PostInteraction.created_at.desc())
        .limit(history_limit)
    )
    # Returns list of tuples: [(post_id, reward), ...]
    return session.exec(statement).all()
