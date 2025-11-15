from sqlmodel import Session, select
from app.models import Reading
import numpy as np
from app.services.item_embeddings import get_all_embeddings
import reading_env


def get_full_reading_by_id(session: Session, id: int) -> Reading:
    return session.exec(select(Reading).where(Reading.id == id)).one()


def get_nearest_readings(
    session: Session,
    model_action_emb: np.ndarray,
    k: int = 3
) -> list["Reading"]:
    # Load embeddings + IDs
    item_embeddings, item_ids = get_all_embeddings(session)
    num_items, dim = item_embeddings.shape

    # Compute logits
    logits = item_embeddings @ model_action_emb

    # Convert logits → probabilities
    probs = reading_env.softmax(logits)

    # Normalize (just in case softmax returned float issues)
    probs = probs / probs.sum()

    # Sample k items from multinomial distribution
    rng = np.random.default_rng()
    sampled_indices = rng.choice(
        num_items,
        size=k,
        replace=False,
        p=probs
    )

    # Convert embedding-row-index → item_id
    sampled_item_ids = [item_ids[i] for i in sampled_indices]

    # Fetch full Reading objects
    readings = [
        get_full_reading_by_id(session, id=item_id)
        for item_id in sampled_item_ids
    ]

    return readings