from sqlmodel import Session

from app.services import memory_service


def get_recent_mistakes(
    session: Session, learner_id: int, limit: int = 5
) -> dict:
    limit = max(1, min(int(limit or 5), 20))
    records = memory_service.get_recent_mistakes(
        session, learner_id, limit=limit
    )
    items = [memory_service.mistake_to_dict(m) for m in records]

    by_type: dict[str, int] = {}
    by_grammar: dict[str, int] = {}
    for m in items:
        by_type[m["mistake_type"]] = by_type.get(m["mistake_type"], 0) + 1
        gp = m.get("grammar_point")
        if gp:
            by_grammar[gp] = by_grammar.get(gp, 0) + 1

    return {
        "ok": True,
        "tool": "get_recent_mistakes",
        "summary": (
            f"Lấy {len(items)} lỗi gần nhất"
            if items
            else "Chưa ghi nhận lỗi nào"
        ),
        "data": {
            "mistakes": items,
            "by_type": by_type,
            "by_grammar_point": by_grammar,
        },
    }
