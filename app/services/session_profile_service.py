from datetime import datetime, timezone

import numpy as np
from numpy.typing import NDArray
from sqlmodel import Session

from app.database import SessionProfile
from app.schemas import InteractionType
from utils import np_utils


def calculate_incremental_mean(
    current_mean: NDArray, new_vector: NDArray, count: int
) -> NDArray:
    """
    Standard incremental mean: O(1) update.
    """
    return current_mean + (new_vector - current_mean) / count


def calculate_interaction_rating(
    interaction_type: InteractionType,
    duration: float | None = None,
) -> float:
    """
    Convert a raw interaction into a signed numeric rating in [-1, 1].

    Meaning:
    - positive values = user seems interested
    - negative values = user seems uninterested / rejecting
    - 0 = neutral / unknown

    Suggested mapping:
    - LIKE: strong positive
    - ADD: positive
    - LISTEN: weak-to-medium positive
    - VIEW_TRANSLATION: medium positive
    - DISLIKE: strong negative
    - REMOVE_REACTION: neutral here, because this function is stateless
    - TIME_SPENT: derived from duration

    For TIME_SPENT, we use a smooth score and keep it in range [-0.8, 0.7]:
        tanh((duration - 3) / 3)

    So:
    - very short time -> negative
    - around 3 seconds -> near 0
    - longer time -> positive
    """
    if interaction_type == InteractionType.LIKE:
        return 1.0

    if interaction_type == InteractionType.ADD:
        return 0.8

    if interaction_type == InteractionType.VIEW_TRANSLATION:
        return 0.6

    if interaction_type == InteractionType.LISTEN:
        return 0.5

    if interaction_type == InteractionType.DISLIKE:
        return -1.0

    if interaction_type == InteractionType.REMOVE_REACTION:
        return 0.0

    if interaction_type == InteractionType.TIME_SPENT:
        if duration is None or duration <= 0:
            return 0.0

        time_rating = np.tanh((duration - 3.0) / 3.0)
        return float(np.clip(time_rating, -0.8, 0.7))

    return 0.0


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
    Apply a single incremental Rocchio-style update.

    This is a simple online variant, not the original batch Rocchio algorithm.

    Update rules:
    - positive interaction:
        new_profile = alpha * current_profile + beta * new_item_vec

    - negative interaction:
        new_profile = alpha * current_profile - gamma * new_item_vec

    - neutral / unknown interaction:
        return current_profile unchanged

    Notes:
    - `alpha` controls how much old preference is kept.
    - `beta` controls how strongly positive items are added.
    - `gamma` controls how strongly negative items are pushed away.
    """
    rating = calculate_interaction_rating(interaction_type, duration)

    if rating > 0:
        return (alpha * current_profile) + (beta * new_item_vec)

    if rating < 0:
        return (alpha * current_profile) - (gamma * new_item_vec)

    return current_profile.copy()


def calculate_weighted_rocchio_update(
    current_profile: NDArray,
    new_item_vec: NDArray,
    interaction_type: InteractionType,
    duration: float | None = None,
    alpha: float = 0.8,
    beta: float = 0.2,
    gamma: float = 0.9,
    similarity_scale: float = 1.0,
    rating_scale: float = 1.0,
) -> NDArray:
    """
    Apply a weighted incremental Rocchio update.

    This version is different from `calculate_rocchio_update()` because it does
    not treat all interactions equally.

    It first converts the interaction into a numeric rating in [-1, 1], then
    computes an influence factor from:

    - similarity between `current_profile` and `new_item_vec`
    - strength of the interaction rating

    Formula idea:
        influence = exp(similarity_scale * cosine_similarity(current, item))
                   * exp(rating_scale * abs(rating))

    Then:
    - positive update:
        new_profile = alpha * current_profile + beta * influence * new_item_vec

    - negative update:
        new_profile = alpha * current_profile - gamma * influence * new_item_vec

    Why this is useful:
    - strong positive interactions affect the profile more
    - weak interactions affect it less
    - highly relevant items can have more influence than random ones
    - the model can adapt better to concept drift

    Parameters:
    - similarity_scale: how strongly similarity affects influence
    - rating_scale: how strongly interaction strength affects influence
    """
    rating = calculate_interaction_rating(interaction_type, duration)

    if rating == 0:
        return current_profile.copy()

    similarity = np_utils.cosine_sim(current_profile, new_item_vec)

    # Exponential influence terms.
    # Similarity contributes because a more similar item should influence the
    # profile more strongly.
    # Rating contributes because a stronger interaction should matter more.
    similarity_factor = float(np.exp(similarity_scale * abs(similarity)))
    rating_factor = float(np.exp(rating_scale * abs(rating)))

    influence = similarity_factor * rating_factor

    weighted_item_vec = new_item_vec * influence

    if rating > 0:
        return (alpha * current_profile) + (beta * weighted_item_vec)

    return (alpha * current_profile) - (gamma * weighted_item_vec)


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

    current_profile = np.frombuffer(profile.profile_vector, np.float64)
    profile.interaction_count += 1
    print(f"current_profile sum: {np.sum(current_profile)}")

    updated_profile = calculate_weighted_rocchio_update(
        current_profile=current_profile,
        new_item_vec=new_snippet_embedding,
        interaction_type=interaction_type,
        duration=duration,
    )

    profile.profile_vector = updated_profile.astype(np.float64).tobytes()
    profile.updated_at = datetime.now(timezone.utc)
    db_session.add(profile)

    if commit:
        db_session.commit()
