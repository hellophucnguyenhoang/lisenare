from sqlmodel import Session, select

from database import Brick, BrickReaction
from schemas import BrickRead


def get_reaction_map(
    session: Session,
    brick_ids: list[int],
    learner_id: int | None,
) -> dict[int, str]:
    if not learner_id or not brick_ids:
        return {}

    rows = session.exec(
        select(BrickReaction.brick_id, BrickReaction.reaction).where(
            BrickReaction.learner_id == learner_id,
            BrickReaction.brick_id.in_(brick_ids),
        )
    ).all()

    return {brick_id: reaction for brick_id, reaction in rows}


def attach_reactions(
    session: Session,
    bricks: list[Brick],
    learner_id: int | None,
) -> list[BrickRead]:
    brick_ids = [b.id for b in bricks if b.id is not None]
    reaction_map = get_reaction_map(session, brick_ids, learner_id)
    return [
        BrickRead.model_validate(
            b,
            update={"reaction": reaction_map.get(b.id)},
        )
        for b in bricks
    ]


def hydrate_reactions(
    session: Session,
    bricks: list[BrickRead],
    learner_id: int | None,
) -> list[BrickRead]:
    brick_ids = [b.id for b in bricks if b.id is not None]
    reaction_map = get_reaction_map(session, brick_ids, learner_id)

    for b in bricks:
        b.reaction = reaction_map.get(b.id)

    return bricks
