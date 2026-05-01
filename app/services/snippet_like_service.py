from sqlmodel import Session, select

from app.database import Snippet, SnippetLike
from app.schemas import SnippetRead


def apply_like_state(
    session: Session,
    snippets: list[Snippet],
    learner_id: int | None,
) -> list[SnippetRead]:

    # Anonymous user -> all False
    if not learner_id:
        return [
            SnippetRead.model_validate(s, update={"is_liked": False})
            for s in snippets
        ]

    # Get snippet IDs
    snippet_ids = [s.id for s in snippets]

    # Fetch liked IDs in one query
    liked_ids = set(
        session.exec(
            select(SnippetLike.snippet_id).where(
                SnippetLike.learner_id == learner_id,
                SnippetLike.snippet_id.in_(snippet_ids),
            )
        ).all()
    )

    # Map to response
    return [
        SnippetRead.model_validate(
            s,
            update={"is_liked": (s.id in liked_ids)},
        )
        for s in snippets
    ]


def apply_like_state_to_reads(
    session: Session,
    snippets: list[SnippetRead],
    learner_id: int | None,
) -> list[SnippetRead]:

    if not snippets:
        return []

    # Anonymous -> all False
    if not learner_id:
        for s in snippets:
            s.is_liked = False
        return snippets

    snippet_ids = [s.id for s in snippets]

    liked_ids = set(
        session.exec(
            select(SnippetLike.snippet_id).where(
                SnippetLike.learner_id == learner_id,
                SnippetLike.snippet_id.in_(snippet_ids),
            )
        ).all()
    )

    # mutate in-place (clean + efficient)
    for s in snippets:
        s.is_liked = s.id in liked_ids

    return snippets
