import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from app.database import SessionProfile, Snippet, SnippetInteraction
from app.services.context_search_service import context_search_service

from . import context_search_service as search_service


def get_random_snippets(
    session: Session,
    limit: int = 5,
) -> list[Snippet]:
    query = (
        select(Snippet)
        .options(selectinload(Snippet.creator))
        .order_by(func.random())
        .limit(limit)
    )
    snippets = session.exec(query).all()
    return snippets


def get_recommended_snippets(
    session: Session,
    session_id: str,
    limit: int = 5,
) -> list[Snippet]:
    """
    Get most relevant snippets to the profile_vector of a session_id.
    Recommend randomly for the first time.
    """
    seen_query = select(SnippetInteraction.snippet_id).where(
        SnippetInteraction.session_id == session_id
    )
    seen_ids = session.exec(seen_query).all()

    profile = session.get(SessionProfile, session_id)
    if profile:
        vector = np.frombuffer(
            profile.profile_vector, dtype=np.float64
        ).tolist()
    else:
        return get_random_snippets(session, limit)

    snippet_ids = context_search_service.get_relevant_snippets(
        vector, limit=limit, exclude_ids=seen_ids
    )
    if not snippet_ids:
        return get_random_snippets(session, limit)

    # Preserving the order of snippet_ids in the  provided relevance order
    order_preserved = case(
        {id_: index for index, id_ in enumerate(snippet_ids)}, value=Snippet.id
    )

    query = (
        select(Snippet)
        .where(Snippet.id.in_(snippet_ids))
        .options(selectinload(Snippet.creator))
        .order_by(order_preserved)
    )

    return session.exec(query).all()


def create_snippet(
    session: Session,
    content: str,
    audio_path: str,
    creator_id: int,
    translation: str | None = None,
) -> Snippet:
    snippet = Snippet(
        content=content,
        audio_path=audio_path,
        creator_id=creator_id,
        translation=translation,
    )

    session.add(snippet)
    session.commit()
    session.refresh(snippet)

    search_service.add_item_to_vector_store(
        search_service=search_service,
        item=snippet,
        store_key="snippets",
        text_getter=lambda s: s.content,
        metadata_getter=lambda s: {"snippet_id": s.id},
        id_prefix="Snippet",
    )
    return snippet


def get_snippet_by_audio_path(
    session: Session,
    audio_path: str,
) -> Snippet | None:
    query = (
        select(Snippet)
        .where(Snippet.audio_path == audio_path)
        .options(selectinload(Snippet.creator))
    )
    snippet = session.exec(query).first()
    if not snippet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snippet with audio path '{audio_path}' not found",
        )
    return snippet
