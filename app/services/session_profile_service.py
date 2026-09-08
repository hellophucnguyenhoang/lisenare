from datetime import datetime, timezone

import numpy as np
from numpy.typing import NDArray
from sqlmodel import Session

from app.config import settings
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


def calculate_interaction_rating(interaction_type: InteractionType) -> float:
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

    return 0.0


def calculate_rocchio_update(
    current_profile: NDArray,
    new_item_vec: NDArray,
    interaction_type: InteractionType,
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
    rating = calculate_interaction_rating(interaction_type)

    if rating > 0:
        return (alpha * current_profile) + (beta * new_item_vec)

    if rating < 0:
        return (alpha * current_profile) - (gamma * new_item_vec)

    return current_profile.copy()


def calculate_weighted_rocchio_update(
    current_profile: NDArray,
    new_item_vec: NDArray,
    interaction_type: InteractionType,
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
    rating = calculate_interaction_rating(interaction_type)

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


def get_random_embedding(dim: int = settings.semantic_emb_dim) -> NDArray:
    """
    Generate a unit-normalized random embedding vector with reasonable range.
    """
    vec = np.random.randn(dim)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float64)


def update_session_profile(
    db_session: Session,
    session_id: str,
    new_brick_embedding: NDArray,
    interaction_type: InteractionType,
    commit: bool = True,
):
    profile = db_session.get(SessionProfile, session_id)
    if not profile:
        initial_vector = get_random_embedding(settings.semantic_emb_dim)
        profile = SessionProfile(
            session_id=session_id,
            profile_vector=initial_vector.tobytes(),
            interaction_count=0,
        )

    current_profile = np.frombuffer(profile.profile_vector, np.float64)
    profile.interaction_count += 1

    updated_profile = calculate_weighted_rocchio_update(
        current_profile=current_profile,
        new_item_vec=new_brick_embedding,
        interaction_type=interaction_type,
    )

    profile.profile_vector = updated_profile.astype(np.float64).tobytes()
    profile.updated_at = datetime.now(timezone.utc)
    db_session.add(profile)

    if commit:
        db_session.commit()
