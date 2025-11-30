from sqlmodel import Session, select
from app.models import Reading, User
import numpy as np
from np_utils import top_k_nearest_idx
from app.services.item_embeddings import get_all_embeddings, get_candidate_embeddings


def get_full_reading_by_id(session: Session, id: int) -> Reading:
    return session.exec(select(Reading).where(Reading.id == id)).one()

def get_nearest_readings(
    session: Session,
    model_action_emb: np.ndarray,
    k: int = 3
):
    item_embeddings, item_ids = get_all_embeddings(session)
    topk_idx = top_k_nearest_idx(item_embeddings, model_action_emb, k)
    topk_item_ids = [item_ids[i] for i in topk_idx]

    return [
        get_full_reading_by_id(session, id=item_id)
        for item_id in topk_item_ids
    ]

def get_relatest_readings(session: Session, model_action_emb: np.ndarray, preferred_topic_ids: list[int], recent_item_ids: list[int], recent_embs: list[np.ndarray], batch_size: int = 3):
    # Retrival phase
    item_embeddings, item_ids = get_candidate_embeddings(session, preferred_topic_ids, recent_item_ids, recent_embs)
    print(f"item_ids:{item_ids}")
    # Ranking phase
    topk_idx = top_k_nearest_idx(item_embeddings, model_action_emb, k=batch_size)
    print(f"topk_idx:{topk_idx}")
    topk_item_ids = [item_ids[i] for i in topk_idx]
    print(f"topk_item_ids:{topk_item_ids}")
    return [
        get_full_reading_by_id(session, id=item_id)
        for item_id in topk_item_ids
    ]