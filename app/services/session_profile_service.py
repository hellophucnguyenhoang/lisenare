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

    # Define which interactions are "Interested" vs "Not Interested"
    interested_types = {
        InteractionType.LIKE,
        InteractionType.ADD,
        InteractionType.LISTEN,
        InteractionType.TIME_SPENT,
    }
    disinterested_types = {InteractionType.UNLIKE}

    if interaction_type in interested_types:
        return (alpha * current_profile) + (beta * new_item_vec)

    elif interaction_type in disinterested_types:
        return (alpha * current_profile) - (gamma * new_item_vec)

    return current_profile


def update_session_profile(
    db_session: Session,
    session_id: str,
    new_snippet_embedding: NDArray,
    interaction_type: InteractionType,
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
    )

    profile.profile_vector = updated_profile.astype(np.float64).tobytes()
    profile.updated_at = datetime.now(timezone.utc)
    if commit:
        db_session.commit()
