from sqlmodel import Session

from app.services.context_search_service import context_search_service


def search_snippet(session: Session, query: str, limit: int = 5) -> dict:
    if not query or not query.strip():
        return {
            "ok": False,
            "tool": "search_snippet",
            "summary": "Query rỗng",
            "error": "empty query",
        }
    query = query.strip()
    limit = max(1, min(int(limit or 5), 10))

    try:
        snippets = context_search_service.search_snippets(session, query)
    except Exception as exc:
        return {
            "ok": False,
            "tool": "search_snippet",
            "summary": f"Lỗi tìm snippet: {exc}",
            "error": str(exc),
        }

    items = []
    for s in snippets[:limit]:
        items.append(
            {
                "id": s.id,
                "content": s.content,
                "translation": s.translation,
                "audio_path": s.audio_path,
                "creator": (
                    {"id": s.creator.id, "full_name": s.creator.full_name}
                    if getattr(s, "creator", None)
                    else None
                ),
            }
        )

    return {
        "ok": True,
        "tool": "search_snippet",
        "summary": (
            f"Tìm thấy {len(items)} snippet khớp '{query}'"
            if items
            else f"Không có snippet nào khớp '{query}'"
        ),
        "data": {"query": query, "snippets": items},
    }
