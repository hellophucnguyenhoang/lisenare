import json
import re

from sqlmodel import Session

from app.database import Lesson, Topic
from app.services.llm_service import call_llm
from app.services.theta_learner_lesson_service import (
    get_theta_average_by_leaner,
    theta_to_level,
)


_PROMPT_TEMPLATE = """Bạn là một giáo viên tiếng Anh. Hãy tạo 1 đoạn văn luyện đọc.

Yêu cầu:
- Chủ đề: {topic}
- Ngữ cảnh bổ sung: {extra_context}
- Độ khó CEFR: {level}
- Độ dài: 80-150 từ tiếng Anh
- Sau đoạn văn, viết {question_count} câu hỏi đọc hiểu (tiếng Anh).
- Liệt kê 5-7 từ vựng quan trọng kèm nghĩa tiếng Việt.

Trả về JSON đúng format sau, không thêm bất kỳ chữ nào khác, không markdown:
{{
  "title": "tiêu đề đoạn văn (tiếng Anh)",
  "level": "{level}",
  "passage": "đoạn văn tiếng Anh",
  "questions": ["câu hỏi 1", "câu hỏi 2", ...],
  "vocabulary": [
    {{"word": "từ tiếng Anh", "meaning": "nghĩa tiếng Việt"}}
  ]
}}
"""


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def generate_passage(
    session: Session,
    learner_id: int,
    topic: str,
    theta: float | None = None,
    question_count: int = 3,
    topic_id: int | None = None,
    lesson_id: int | None = None,
) -> dict:
    topic = (topic or "").strip()
    question_count = max(1, min(int(question_count or 3), 5))

    extra_context = ""
    if topic_id is not None:
        db_topic = session.get(Topic, topic_id)
        if db_topic:
            if not topic:
                topic = db_topic.name
            extra_context += f"Topic: {db_topic.name}. "
    if lesson_id is not None:
        db_lesson = session.get(Lesson, lesson_id)
        if db_lesson:
            extra_context += f"Lesson: {db_lesson.name}. "

    if not topic:
        return {
            "ok": False,
            "tool": "generate_passage",
            "summary": "Thiếu topic",
            "error": "empty topic",
        }

    if theta is None:
        try:
            theta = get_theta_average_by_leaner(session, learner_id)
        except Exception:
            theta = 0.0
    level = theta_to_level(float(theta or 0.0))

    prompt = _PROMPT_TEMPLATE.format(
        topic=topic, level=level, question_count=question_count,
        extra_context=extra_context,
    )
    raw = call_llm(prompt)
    parsed = _extract_json(raw)

    if not parsed:
        return {
            "ok": False,
            "tool": "generate_passage",
            "summary": "LLM không trả về JSON hợp lệ",
            "data": {"raw": raw[:500] if raw else None},
        }

    return {
        "ok": True,
        "tool": "generate_passage",
        "summary": (
            f"Đã tạo passage chủ đề '{topic}' "
            f"level {level} kèm {len(parsed.get('questions', []))} câu hỏi"
        ),
        "data": {
            "title": parsed.get("title"),
            "level": parsed.get("level", level),
            "passage": parsed.get("passage"),
            "questions": parsed.get("questions", []),
            "vocabulary": parsed.get("vocabulary", []),
        },
    }
