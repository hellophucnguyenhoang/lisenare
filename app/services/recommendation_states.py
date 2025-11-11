from sqlmodel import Session, select
from app.models import User, RecommendationState, Reading
import uuid

# app/services/recommendation_states.py
from sqlmodel import Session, select, func
from app.models import Interaction, RecommendationState
from sqlalchemy import func, case, desc, select
from app.core.security import get_password_hash
from .item_embeddings import get_all_item_embeddings
from reading_rec_env import REWARD_MAP


def get_latest_recommendation_state(session: Session, user_id: int, interacted_only: bool = True) -> RecommendationState | None:
    stmt = (
        select(RecommendationState, Interaction)
        .join(Interaction)
        .where(RecommendationState.user_id == user_id)
        .order_by(RecommendationState.created_at.desc())
    )
    batches = session.exec(stmt).all()
    if not batches:
        return None
    
    latest_batch_id = batches[0][0].batch_id
    highest_reward = float("-inf")
    latest_rs = None
    for rs, inter in batches:
        print(f"RS:{rs}, INTER:{inter}, REWARD:{REWARD_MAP[inter.event_type]}, highest_reward:{highest_reward}")
        if rs.batch_id != latest_batch_id:
            break
        if REWARD_MAP[inter.event_type] > highest_reward:
            
            highest_reward = REWARD_MAP[inter.event_type]
            latest_rs = rs
            print('Update latest_rs to:', latest_rs)
    return latest_rs


def generate_batch_id() -> str:
    return str(uuid.uuid4())  # generate a unique string for each batch


def create_recommendation_states(session: Session, user: User, recommended_nearest_readings: list[Reading], max_items: int = 5) -> list[RecommendationState]:
    """
    Append new item_ids to the user's state sequence for each recommendation,
    but do NOT mutate the original current_ids. Each new RecommendationState
    uses current_ids + [item_id] (trimmed to max_items with FIFO if necessary).
    """
    batch_id = generate_batch_id()

    latest_rs = get_latest_recommendation_state(session, user.id)
    print(f"LATEST_RS:{latest_rs}")
    recommendation_states: list[RecommendationState] = []

    # Nếu user chưa có state nào -> tạo state mới với mỗi reading (chứa 1 id)
    if not latest_rs:
        for reading in recommended_nearest_readings:
            item_id = reading.id
            rs = RecommendationState(
                user_id=user.id,
                item_ids=str(item_id),
                batch_id=batch_id
            )
            recommendation_states.append(rs)

        session.add_all(recommendation_states)
        session.commit()
        for rs in recommendation_states:
            session.refresh(rs)
        return recommendation_states

    # Nếu đã có state cũ -> lấy current_ids (KHÔNG mutate)
    current_ids = [x.strip() for x in latest_rs.item_ids.split(",") if x.strip()]

    for reading in recommended_nearest_readings:
        item_id = reading.id

        # Tạo danh sách mới cho state này, không thay đổi current_ids gốc
        new_ids = current_ids + [str(item_id)]

        # Nếu dài hơn max_items thì giữ phần cuối (FIFO)
        if len(new_ids) > max_items:
            new_ids = new_ids[-max_items:]

        rs = RecommendationState(
            user_id=user.id,
            item_ids=",".join(new_ids),
            batch_id=batch_id
        )
        recommendation_states.append(rs)

    session.add_all(recommendation_states)
    session.commit()
    for rs in recommendation_states:
        session.refresh(rs)

    return recommendation_states

