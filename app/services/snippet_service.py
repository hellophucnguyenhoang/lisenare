from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from app.database import Snippet


def get_random_snippets(session: Session, limit: int = 20) -> list[Snippet]:
    query = (
        select(Snippet)
        .options(selectinload(Snippet.creator))
        .order_by(func.random())
        .limit(limit)
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
    return snippet


# NOT USED
def get_snippets_by_ids(
    session: Session,
    snippet_ids: list[int],
):
    query = (
        select(Snippet)
        .where(Snippet.id.in_(snippet_ids))
        .options(selectinload(Snippet.creator))
    )
    snippets = session.exec(query).all()
    return snippets


# NOT USED
def get_candidate_pool(
    session: Session, limit: int = 100, exclude_ids: list[int] | None = None
):
    """
    Fetches a random pool of candidate snippets,
    optionally excluding specific IDs (e.g., already seen).
    """
    query = (
        select(Snippet)
        .options(selectinload(Snippet.creator))
        .order_by(func.random())  # Efficient random sampling at DB level
        .limit(limit)
    )

    if exclude_ids:
        query = query.where(Snippet.id.not_in(exclude_ids))

    return session.exec(query).all()
