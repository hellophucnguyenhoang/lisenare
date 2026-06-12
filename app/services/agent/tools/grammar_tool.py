import json

from sqlmodel import Session

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
