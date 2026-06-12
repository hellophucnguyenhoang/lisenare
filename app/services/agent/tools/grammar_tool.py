import json

from sqlmodel import Session, or_, select

from app.database import Concept, Lesson, Topic
from app.services.lesson_service import get_all_lesson_by_topic_id
from app.services.topic_service import get_all_topic


def get_topics_lesson(session: Session) -> str:
    """Liệt kê toàn bộ topic + lesson hệ thống."""
    topics = get_all_topic(session)
    topic_list = []
    total_lessons = 0
    for topic in topics:
        lessons = get_all_lesson_by_topic_id(session, topic.id)
        lesson_data = [
            {"id": lesson.id, "name": lesson.name} for lesson in lessons
        ]
        total_lessons += len(lesson_data)
        topic_list.append(
            {
                "id": topic.id,
                "name": topic.name,
                "total_lessons": len(lesson_data),
                "lessons": lesson_data,
            }
        )

    result = {
        "status": "success" if topic_list else "empty",
        "total_topics": len(topic_list),
        "total_lessons": total_lessons,
        "topics": topic_list,
    }
    return json.dumps(result, ensure_ascii=False)


def search_grammar(session: Session, query: str, limit: int = 8) -> dict:
    """Tìm Concept ngữ pháp khớp query (LIKE trên name + description),
    kèm Lesson chứa concept đó."""
    if not query or not query.strip():
        return {
            "ok": False,
            "tool": "search_grammar",
            "summary": "Query rỗng",
            "error": "empty query",
        }
    q = query.strip()
    pattern = f"%{q}%"

    statement = (
        select(Concept, Lesson, Topic)
        .join(Lesson, Concept.lesson_id == Lesson.id, isouter=True)
        .join(Topic, Lesson.topic_id == Topic.id, isouter=True)
        .where(
            or_(
                Concept.name.ilike(pattern),
                Concept.description.ilike(pattern),
            )
        )
        .limit(limit)
    )
    rows = session.exec(statement).all()

    matched = []
    related_lessons = {}
    for concept, lesson, topic in rows:
        matched.append(
            {
                "concept_id": concept.id,
                "name": concept.name,
                "type": concept.type,
                "description": concept.description,
                "lesson_id": lesson.id if lesson else None,
                "lesson_name": lesson.name if lesson else None,
            }
        )
        if lesson and lesson.id not in related_lessons:
            related_lessons[lesson.id] = {
                "lesson_id": lesson.id,
                "lesson_name": lesson.name,
                "topic_name": topic.name if topic else None,
            }

    return {
        "ok": True,
        "tool": "search_grammar",
        "summary": (
            f"Tìm thấy {len(matched)} concept khớp '{q}'"
            if matched
            else f"Không có concept nào khớp '{q}'"
        ),
        "data": {
            "query": q,
            "matched_concepts": matched,
            "related_lessons": list(related_lessons.values()),
        },
    }
