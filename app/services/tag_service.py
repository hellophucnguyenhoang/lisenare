from sqlmodel import Session, col, select

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


def fetch_tags_for_entity(
    session: Session, entity_id: int, entity_type: str
) -> list[str]:
    """Fetches list of tag names for a single entity."""
    tags_map = fetch_tags_for_entities(session, [entity_id], entity_type)
    return tags_map.get(entity_id, [])


def set_tags_for_entity(
    session: Session,
    entity_id: int,
    entity_type: str,
    tag_names: list[str],
    creator_id: int,
) -> list[str]:
    """Sets (replaces) tags for a specific entity, creating new Tag records if needed."""
    delete_tags_for_entity(session, entity_id, entity_type)

    cleaned_tags: list[str] = []
    seen: set[str] = set()
    for name in tag_names:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cleaned_tags.append(cleaned)

    if not cleaned_tags:
        return []

    existing_tags = session.exec(
        select(Tag).where(
            Tag.creator_id == creator_id,
            col(Tag.name).in_(cleaned_tags),
        )
    ).all()
    tag_by_name = {t.name: t for t in existing_tags}

    for tag_name in cleaned_tags:
        if tag_name not in tag_by_name:
            new_tag = Tag(name=tag_name, creator_id=creator_id)
            session.add(new_tag)
            session.flush()
            tag_by_name[tag_name] = new_tag

    for tag_name in cleaned_tags:
        tag = tag_by_name[tag_name]
        taggable = Taggable(
            tag_id=tag.id,
            taggable_id=entity_id,
            taggable_type=entity_type,
        )
        session.add(taggable)

    return cleaned_tags


def delete_tags_for_entity(
    session: Session, entity_id: int, entity_type: str
) -> None:
    """Deletes all taggable entries for a specific entity."""
    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == entity_id,
            Taggable.taggable_type == entity_type,
        )
    ).all()
    for taggable in taggables:
        session.delete(taggable)
