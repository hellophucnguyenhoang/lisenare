from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from app.database import Snippet


def get_random_snippets(
    session: Session,
    limit: int = 20,
) -> list[Snippet]:
    query = (
        select(Snippet)
        .options(selectinload(Snippet.creator))
        .order_by(func.random())
        .limit(limit)
    )
    snippets = session.exec(query).all()
    return snippets


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
