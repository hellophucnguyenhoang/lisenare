from sqlmodel import Session, select

from app.database import Snippet, SnippetReaction
from app.schemas import SnippetRead


def get_reaction_map(
    session: Session,
    snippet_ids: list[int],
    learner_id: int | None,
) -> dict[int, str]:
    if not learner_id or not snippet_ids:
        return {}

    rows = session.exec(
        select(SnippetReaction.snippet_id, SnippetReaction.reaction).where(
            SnippetReaction.learner_id == learner_id,
            SnippetReaction.snippet_id.in_(snippet_ids),
        )
    ).all()

    return {snippet_id: reaction for snippet_id, reaction in rows}


def attach_reactions(
    session: Session,
    snippets: list[Snippet],
    learner_id: int | None,
) -> list[SnippetRead]:
    snippet_ids = [s.id for s in snippets]
    reaction_map = get_reaction_map(session, snippet_ids, learner_id)

    return [
        SnippetRead.model_validate(
            s,
            update={"reaction": reaction_map.get(s.id)},
        )
        for s in snippets
    ]


def hydrate_reactions(
    session: Session,
    snippets: list[SnippetRead],
    learner_id: int | None,
) -> list[SnippetRead]:

    if not snippets:
        return []

    snippet_ids = [s.id for s in snippets]
    reaction_map = get_reaction_map(session, snippet_ids, learner_id)

    for s in snippets:
        s.reaction = reaction_map.get(s.id)

    return snippets
