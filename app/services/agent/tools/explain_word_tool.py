import re

from sqlmodel import Session

from app.services.llm_service import call_llm


_CONTEXT_PROMPT = """Bạn là gia sư tiếng Anh. Giải thích nghĩa của từ "{word}" \
TRONG ngữ cảnh sau (không giải thích nghĩa chung chung).

Câu/đoạn ngữ cảnh:
{context}

Trả về theo định dạng XML:
<meaning_vi>nghĩa tiếng Việt trong ngữ cảnh này</meaning_vi>
<paraphrase>diễn giải lại câu trên bằng tiếng Anh đơn giản hơn</paraphrase>
<note>1 lưu ý ngắn (collocation, sắc thái, từ loại) nếu có, hoặc bỏ trống</note>
"""


_GENERIC_PROMPT = """Bạn là gia sư tiếng Anh. Giải thích nghĩa từ "{word}" \
một cách ngắn gọn cho học viên Việt Nam.

Trả về XML:
<meaning_vi>nghĩa chính bằng tiếng Việt</meaning_vi>
<example>1 câu ví dụ tiếng Anh dùng đúng từ</example>
<note>từ loại / sắc thái / collocation đáng chú ý (có thể trống)</note>
"""


def _extract_first_tag(text: str, tag: str) -> str | None:
    if not text:
        return None
    match = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def explain_word_in_context(
    session: Session,
    word: str,
    context: str | None = None,
) -> dict:
    if not word or not word.strip():
        return {
            "ok": False,
            "tool": "explain_word_in_context",
            "summary": "Thiếu từ cần giải thích",
            "error": "empty word",
        }
    word = word.strip()

    if context and context.strip():
        prompt = _CONTEXT_PROMPT.format(word=word, context=context.strip())
        raw = call_llm(prompt)
        return {
            "ok": True,
            "tool": "explain_word_in_context",
            "summary": (
                f"Đã giải thích '{word}' trong ngữ cảnh "
                f"({len(context)} ký tự)"
            ),
            "data": {
                "word": word,
                "context": context,
                "meaning_vi": _extract_first_tag(raw, "meaning_vi"),
                "paraphrase_en": _extract_first_tag(raw, "paraphrase"),
                "note": _extract_first_tag(raw, "note"),
            },
        }

    prompt = _GENERIC_PROMPT.format(word=word)
    raw = call_llm(prompt)
    return {
        "ok": True,
        "tool": "explain_word_in_context",
        "summary": f"Đã giải thích '{word}' (không có ngữ cảnh)",
        "data": {
            "word": word,
            "context": None,
            "meaning_vi": _extract_first_tag(raw, "meaning_vi"),
            "example_en": _extract_first_tag(raw, "example"),
            "note": _extract_first_tag(raw, "note"),
        },
    }
