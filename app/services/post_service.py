from pathlib import Path

from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from app.database import Post


def get_random_posts(session: Session, limit: int = 20):
    query = (
        select(Post)
        .options(selectinload(Post.creator))
        .order_by(func.random())
        .limit(limit)
    )

    return session.exec(query).all()


def get_posts_by_ids(
    session: Session,
    post_ids: list[int],
):
    query = (
        select(Post)
        .where(Post.id.in_(post_ids))
        .options(selectinload(Post.creator))
    )
    posts = session.exec(query).all()
    return posts


def get_candidate_pool(
    session: Session, limit: int = 100, exclude_ids: list[int] | None = None
):
    """
    Fetches a random pool of candidate posts,
    optionally excluding specific IDs (e.g., already seen).
    """
    query = (
        select(Post)
        .options(selectinload(Post.creator))
        .order_by(func.random())  # Efficient random sampling at DB level
        .limit(limit)
    )

    if exclude_ids:
        query = query.where(Post.id.not_in(exclude_ids))

    return session.exec(query).all()


def iter_audio_path(relative_path: str):
    base_dir = Path(relative_path)
    file_path = base_dir.resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file
