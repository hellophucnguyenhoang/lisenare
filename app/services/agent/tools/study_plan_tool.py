import json
import re

from sqlmodel import Session

from app.services import memory_service
from app.services.history_answer_question_service import get_history_by_learner
from app.services.llm_service import call_llm
from app.services.theta_learner_lesson_service import (
    get_theta_average_by_leaner,
    get_theta_info_by_leaner_and_lesson,
    theta_to_level,
)


_PROMPT_TEMPLATE = """Bạn là cố vấn học tập tiếng Anh. Hãy lập kế hoạch học cá nhân hoá.

Mục tiêu: {goal}
Số tuần: {weeks}
Trình độ hiện tại (CEFR): {level} (theta {theta:.2f})

Điểm mạnh / yếu (theo lesson):
{strengths_weaknesses}

Lỗi sai gần đây của học viên:
{recent_mistakes}

Yêu cầu:
- Lập kế hoạch theo tuần, mỗi tuần 1 trọng tâm.
- Đưa ra routine luyện tập hằng ngày.
- 2-3 cột mốc kiểm tra tiến độ.
- Trả lời ngắn gọn, thực tế.

Trả về JSON đúng format, không markdown, không thêm chữ nào khác:
{{
  "goal": "...",
  "weeks": {weeks},
  "weekly_plan": [
    {{"week": 1, "focus": "...", "activities": ["...", "..."]}}
  ],
  "daily_routine": ["...", "..."],
  "milestones": ["...", "..."]
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


def _format_strengths_weaknesses(theta_info: list) -> str:
    if not theta_info:
        return "(chưa có dữ liệu lesson)"
    lines = []
    for row in theta_info[:8]:
        mapping = getattr(row, "_mapping", None)
        get = (
            (lambda k, idx: mapping[k])
            if mapping is not None
            else (lambda k, idx, r=row: getattr(r, k, r[idx]))
        )
        lesson = get("lesson_name", 1)
        topic = get("topic_name", 2)
        theta = get("theta_lesson", 0)
        lines.append(f"- {topic} / {lesson}: theta {float(theta):.2f}")
    return "\n".join(lines)


def _format_recent_mistakes(mistakes: list) -> str:
    if not mistakes:
        return "(chưa có lỗi nào ghi nhận)"
    lines = []
    for m in mistakes[:5]:
        gp = f" [{m.grammar_point}]" if m.grammar_point else ""
        lines.append(f"- {m.mistake_type}{gp}: {m.content[:120]}")
    return "\n".join(lines)


def generate_study_plan(
    session: Session,
    learner_id: int,
    goal: str,
    weeks: int = 4,
) -> dict:
    if not goal or not goal.strip():
        return {
            "ok": False,
            "tool": "generate_study_plan",
            "summary": "Thiếu mục tiêu",
            "error": "empty goal",
        }
    weeks = max(1, min(int(weeks or 4), 24))

    try:
        theta = get_theta_average_by_leaner(session, learner_id) or 0.0
    except Exception:
        theta = 0.0
    level = theta_to_level(float(theta))

    try:
        theta_info = get_theta_info_by_leaner_and_lesson(session, learner_id)
    except Exception:
        theta_info = []

    try:
        recent_mistakes = memory_service.get_recent_mistakes(
            session, learner_id, limit=5
        )
    except Exception:
        recent_mistakes = []

    prompt = _PROMPT_TEMPLATE.format(
        goal=goal.strip(),
        weeks=weeks,
        level=level,
        theta=float(theta),
        strengths_weaknesses=_format_strengths_weaknesses(theta_info),
        recent_mistakes=_format_recent_mistakes(recent_mistakes),
    )

    raw = call_llm(prompt)
    parsed = _extract_json(raw)

    if not parsed:
        return {
            "ok": False,
            "tool": "generate_study_plan",
            "summary": "LLM không trả về JSON hợp lệ",
            "data": {"raw": raw[:500] if raw else None},
        }

    return {
        "ok": True,
        "tool": "generate_study_plan",
        "summary": (
            f"Đã tạo kế hoạch {weeks} tuần cho mục tiêu '{goal}' "
            f"(level hiện tại {level})"
        ),
        "data": {
            "goal": parsed.get("goal", goal),
            "weeks": parsed.get("weeks", weeks),
            "current_level": level,
            "current_theta": float(theta),
            "weekly_plan": parsed.get("weekly_plan", []),
            "daily_routine": parsed.get("daily_routine", []),
            "milestones": parsed.get("milestones", []),
        },
    }
