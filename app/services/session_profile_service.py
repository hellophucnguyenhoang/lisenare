from datetime import datetime, timezone

import numpy as np
from numpy.typing import NDArray
from sqlmodel import Session

from app.database import SessionProfile
from app.schemas import InteractionType


def calculate_incremental_mean(
    current_mean: NDArray, new_vector: NDArray, count: int
) -> NDArray:
    """
    Standard incremental mean: O(1) update.
    """
    return current_mean + (new_vector - current_mean) / count


def calculate_rocchio_update(
    current_profile: NDArray,
    new_item_vec: NDArray,
    interaction_type: InteractionType,
    duration: float | None = None,
    alpha: float = 0.8,
    beta: float = 0.2,
    gamma: float = 0.9,
) -> NDArray:
    """
    Incremental Rocchio update for a single interaction.

    New = (alpha * current) + (beta * liked_item)

    Or

    New = (alpha * current) - (gamma * disliked_item)

    This is not Mathematically Original Rocchio because alpha is added every time
    instead of only the first time, but it's good for "Concept Drift".
    This ensures that the recommendation system remains responsive to the user's evolving interests

    """

    # Group types by the mathematical operation they perform
    positive_interactions = {
        InteractionType.LISTEN,
        InteractionType.VIEW_TRANSLATION,
        InteractionType.LIKE,
        InteractionType.ADD,
    }
    negative_interactions = {InteractionType.DISLIKE}

    # 1. Determine if this interaction is positive or negative
    is_positive = interaction_type in positive_interactions or (
        interaction_type == InteractionType.TIME_SPENT and duration >= 3
    )

    is_negative = interaction_type in negative_interactions or (
        interaction_type == InteractionType.TIME_SPENT and duration < 3
    )

    # 2. Apply the formula based on the direction
    if is_positive:
        return (alpha * current_profile) + (beta * new_item_vec)
    if is_negative:
        return (alpha * current_profile) - (gamma * new_item_vec)

    print(
        f"WARNING: Rocchio update no match: {interaction_type = }, {duration = }"
    )
    return current_profile  # Fallback if no rules matched


def update_session_profile(
    db_session: Session,
    session_id: str,
    new_snippet_embedding: NDArray,
    interaction_type: InteractionType,
    duration: float | None = None,
    initial_mean_path: str = "assets/embeddings/snippets_mean.npy",
    commit: bool = True,
):
    profile = db_session.get(SessionProfile, session_id)
    if not profile:
        initial_mean: np.ndarray = np.load(initial_mean_path)
        print(f"initial_mean sum: {np.sum(initial_mean)}")
        profile = SessionProfile(
            session_id=session_id,
            profile_vector=initial_mean.tobytes(),
            interaction_count=0,
        )
        db_session.add(profile)

    current_profile = np.frombuffer(profile.profile_vector, np.float64)
    profile.interaction_count += 1
    print(f"current_profile sum: {np.sum(current_profile)}")

    updated_profile = calculate_rocchio_update(
        current_profile=current_profile,
        new_item_vec=new_snippet_embedding,
        interaction_type=interaction_type,
        duration=duration,
    )

    profile.profile_vector = updated_profile.astype(np.float64).tobytes()
    profile.updated_at = datetime.now(timezone.utc)
    if commit:
        db_session.commit()
