from sqlmodel import Session

from app.services.context_search_service import (
    context_search_service,
    search_bricks_literal,
)


def lookup_vocabulary(
    session: Session, word: str, limit: int = 5
) -> dict:
    """Tra cứu từ vựng: tìm các brick chứa từ + ngữ cảnh tương tự."""
    if not word or not word.strip():
        return {
            "ok": False,
            "tool": "lookup_vocabulary",
            "summary": "Từ tra cứu rỗng",
            "error": "empty word",
        }

    word = word.strip()

    literal_hits = search_bricks_literal(session, word)[:limit]
    semantic_hits = []
    try:
        semantic_hits = context_search_service.search_bricks_semantic(
            word, mmr=False
        )[:limit]
    except Exception as exc:
        print(f"[lookup_vocabulary] semantic search failed: {exc}")

    seen_ids = set()
    examples = []
    for hit in literal_hits + semantic_hits:
        bid = getattr(hit, "brick_id", None)
        if bid is None or bid in seen_ids:
            continue
        seen_ids.add(bid)
        examples.append(
            {
                "brick_id": bid,
                "target_text": getattr(hit, "target_text", None),
                "native_text": getattr(hit, "native_text", None),
                "cefr_level": getattr(hit, "cefr_level", None),
            }
        )
        if len(examples) >= limit:
            break

    return {
        "ok": True,
        "tool": "lookup_vocabulary",
        "summary": (
            f"Tìm thấy {len(examples)} ví dụ chứa từ '{word}'"
            if examples
            else f"Không tìm thấy ví dụ nào cho '{word}'"
        ),
        "data": {"word": word, "examples": examples},
    }
