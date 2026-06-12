import json
import re

from sqlmodel import Session

from app.services import memory_service
from app.services.llm_service import call_llm


_PROMPT_TEMPLATE = """Bạn là gia sư tiếng Anh. Hãy phân tích lỗi của học viên.

Câu hỏi:
{question}

Câu trả lời của học viên:
{learner_answer}

{correct_block}

Trả về JSON đúng format sau (không thêm chữ nào ngoài JSON, không markdown):
{{
  "mistake_type": "grammar | vocabulary | spelling | logic | other",
  "grammar_point": "tên điểm ngữ pháp liên quan, hoặc null",
  "explanation": "giải thích ngắn (1-2 câu) bằng tiếng Việt vì sao sai",
  "suggested_fix": "câu/đáp án đúng (tiếng Anh)"
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


def analyze_mistake(
    session: Session,
    learner_id: int,
    question: str,
    learner_answer: str,
    correct_answer: str | None = None,
    save: bool = True,
    content_prefix: str | None = None,
) -> dict:
    if not question or not learner_answer:
        return {
            "ok": False,
            "tool": "analyze_mistake",
            "summary": "Thiếu question hoặc learner_answer",
            "error": "missing required fields",
        }

    correct_block = (
        f"Đáp án đúng: {correct_answer}" if correct_answer else ""
    )
    prompt = _PROMPT_TEMPLATE.format(
        question=question,
        learner_answer=learner_answer,
        correct_block=correct_block,
    )

    raw = call_llm(prompt)
    parsed = _extract_json(raw)

    if not parsed:
        return {
            "ok": False,
            "tool": "analyze_mistake",
            "summary": "LLM không trả về JSON hợp lệ",
            "data": {"raw": raw[:500] if raw else None},
        }

    mistake_type = str(parsed.get("mistake_type") or "other")
    grammar_point = parsed.get("grammar_point")
    if isinstance(grammar_point, str) and grammar_point.lower() == "null":
        grammar_point = None
    explanation = parsed.get("explanation") or ""
    suggested_fix = parsed.get("suggested_fix")

    saved_id = None
    if save:
        prefix = content_prefix or ""
        content = (
            f"{prefix}Q: {question}\n"
            f"Learner: {learner_answer}\n"
            f"Explain: {explanation}"
        )
        try:
            record = memory_service.add_mistake(
                session,
                learner_id=learner_id,
                mistake_type=mistake_type,
                content=content,
                grammar_point=grammar_point,
                suggested_fix=suggested_fix,
            )
            saved_id = record.id
        except Exception as exc:
            print(f"[analyze_mistake] save failed: {exc}")

    return {
        "ok": True,
        "tool": "analyze_mistake",
        "summary": (
            f"Lỗi loại '{mistake_type}'"
            + (f" về '{grammar_point}'" if grammar_point else "")
        ),
        "data": {
            "mistake_type": mistake_type,
            "grammar_point": grammar_point,
            "explanation": explanation,
            "suggested_fix": suggested_fix,
            "saved": saved_id is not None,
            "memory_id": saved_id,
        },
    }

