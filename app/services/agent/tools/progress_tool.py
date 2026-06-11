from app.services.theta_learner_lesson_service import (
    get_theta_average_by_leaner,
    get_theta_info_by_leaner_and_lesson,
)
from sqlmodel import Session


def get_user_progress(session: Session, learner_id: int):
    theta_average = get_theta_average_by_leaner(session, learner_id)
    theta_info = get_theta_info_by_leaner_and_lesson(session, learner_id)
    lessons = [convert_theta_lesson(info) for info in theta_info]
    return {
        "ok": True,
        "tool": "get_user_progress",
        "summary": (
            f"User has an average theta of {theta_average:.2f} "
            f"across {len(lessons)} lessons"
        ),
        "data": {
            "theta_average": theta_average,
            "theta_info": lessons,
        },
    }


def convert_theta_lesson(theta_info):
    if theta_info is None:
        return None
    return {
        "theta_lesson": get_row_value(theta_info, "theta_lesson", 0),
        "lesson_name": get_row_value(theta_info, "lesson_name", 1),
        "topic_name": get_row_value(theta_info, "topic_name", 2),
        "lesson_description": get_row_value(
            theta_info, "lesson_description", 3
        ),
        "topic_description": get_row_value(theta_info, "topic_description", 4),
    }


def get_row_value(row, key: str, index: int):
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    value = getattr(row, key, None)
    if value is not None:
        return value
    return row[index]
