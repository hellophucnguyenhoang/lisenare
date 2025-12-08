from sqlmodel import Session, select
from app.models import StudySession
from . import item_embeddings as item_embeddings_services
from fastapi import HTTPException
from reading_env import EVENT_REWARD_MAP
from datetime import datetime, timezone
from app.config import settings


def get_all_submitted_sessions(session: Session, user_id: int):
    stmt = (
        select(StudySession)
        .where(StudySession.user_id == user_id)
        .where(StudySession.last_event_type.in_(["submit", "like", "dislike"]))
        .order_by(StudySession.last_update.desc())
    )
    return session.exec(stmt).all()

def get_by_id(session: Session, id: int):
    stmt = (
        select(StudySession)
        .where(StudySession.id == id)
    )
    return session.exec(stmt).first()

def get_user_recent_study_sessions(session: Session, user_id: int, recent_history_size: int = settings.recent_history_size):
    # 1. GET the latest 5 batches (by last_update)
    stmt_batches = (
        select(StudySession.batch_id)
        .where(StudySession.user_id == user_id)
        .group_by(StudySession.batch_id)
        .order_by(StudySession.last_update.desc())
        .limit(recent_history_size)
    )
    
    latest_batches = [row for row in session.exec(stmt_batches).all()]
    if not latest_batches:
        return []

    # 2. GET all study sessions from those batches
    stmt_sessions = (
        select(StudySession)
        .where(StudySession.batch_id.in_(latest_batches), StudySession.last_event_type.is_not(None))
        .order_by(StudySession.last_update.desc())
    )

    sessions = session.exec(stmt_sessions).all()

    # 3. GROUP by batch_id and pick the highest reward
    best_per_batch = {}
    for ss in sessions:
        if ss.batch_id not in best_per_batch:
            best_per_batch[ss.batch_id] = ss
        else:
            # pick the one with the higher reward
            reward = EVENT_REWARD_MAP[ss.last_event_type]
            if reward > EVENT_REWARD_MAP[best_per_batch[ss.batch_id].last_event_type]:
                best_per_batch[ss.batch_id] = ss

    # 4. Sort by time (oldest → newest)
    result = sorted(best_per_batch.values(), key=lambda s: s.last_update)
    return result

def get_recent_history(session: Session, user_id: int):
    """
    The last item in the history is treated as the 'new' item by default.  
    'new' means the item use was interacted and we need to update user preference for it.
    """

    user_recent_study_sessions = get_user_recent_study_sessions(session, user_id, recent_history_size=settings.recent_history_size + 1)
    recent_item_ids = []
    recent_embs = []
    recent_rewards = []
    for study_session in user_recent_study_sessions:
        item_emb = item_embeddings_services.get_embedding_by_reading_id(session, study_session.reading_id)
        reward = EVENT_REWARD_MAP[study_session.last_event_type]
        recent_item_ids.append(study_session.reading_id)
        recent_embs.append(item_emb)
        recent_rewards.append(reward)

    return recent_item_ids, recent_embs, recent_rewards

def create_batch(session: Session, user_id: int, item_ids: list[int]):
    study_sessions = []

    # Create the first session (batch_id auto-generated)
    first_session = StudySession(
        user_id=user_id,
        reading_id=item_ids[0],
    )
    session.add(first_session)
    session.flush()        # generate batch_id
    batch_id = first_session.batch_id
    study_sessions.append(first_session)

    # Create the remaining sessions in the same batch
    for item_id in item_ids[1:]:
        study_sessions.append(
            StudySession(
                user_id=user_id,
                reading_id=item_id,
                batch_id=batch_id,
            )
        )

    # Add all at once
    session.add_all(study_sessions[1:])
    session.commit()

    # Refresh all
    for ss in study_sessions:
        session.refresh(ss)
    return study_sessions

def update_event(session: Session, study_session_id: int, event_type: str):
    study_session = session.get(StudySession, study_session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="StudySession not found")
    
    study_session.last_event_type = event_type
    study_session.last_update = datetime.now(timezone.utc)

    session.add(study_session)
    session.commit()
    session.refresh(study_session)
    return study_session

def submit_answer(session: Session, study_session_id: int, user_answers: str):
    study_session = session.get(StudySession, study_session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")

    study_session.user_answers = user_answers
    study_session.last_event_type = "submit"
    study_session.last_update = datetime.now(timezone.utc)

    session.add(study_session)
    session.commit()
    session.refresh(study_session)
    return study_session
