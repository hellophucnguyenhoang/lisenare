from sqlmodel import Session, select

from app.database import Tag, Taggable


def fetch_tags_for_entities(
    session: Session, entity_ids: list[int], entity_type: str
) -> dict[int, list[str]]:
    """Fetches and maps tags for a list of entity IDs (can be empty) based on their type."""
    if not entity_ids:
        return {}

    tags_data = session.exec(
        select(Taggable.taggable_id, Tag.name)
        .join(Tag, Taggable.tag_id == Tag.id)
        .where(
            Taggable.taggable_id.in_(entity_ids),
            Taggable.taggable_type == entity_type,
        )
    ).all()

    mapped_tags: dict[int, list[str]] = {
        entity_id: [] for entity_id in entity_ids
    }
    for entity_id, tag_name in tags_data:
        mapped_tags.setdefault(entity_id, []).append(tag_name)

    return mapped_tags
