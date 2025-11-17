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
):
    item_embeddings, item_ids = get_all_embeddings(session)

    # Normalize embeddings for cosine similarity
    item_norms = item_embeddings / np.linalg.norm(item_embeddings, axis=1, keepdims=True)
    action_norm = model_action_emb / np.linalg.norm(model_action_emb)

    # Cosine similarity
    sims = item_norms @ action_norm  # shape: (num_items,)

    # Take top-k
    topk_idx = np.argsort(sims)[::-1][:k]

    topk_item_ids = [item_ids[i] for i in topk_idx]

    return [
        get_full_reading_by_id(session, id=item_id)
        for item_id in topk_item_ids
    ]
