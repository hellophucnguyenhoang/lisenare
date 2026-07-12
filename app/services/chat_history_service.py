"""Lưu trữ lịch sử chat chatbot: nội dung tin nhắn lưu thành object JSON trên
Cloudflare R2 theo từng phiên, key của object được ghi vào bảng ``historychat``
của DB.

Mỗi *phiên chat* (session) là một cuộc trò chuyện độc lập, ứng với **một row**
trong bảng ``historychat`` và **một object JSON riêng** trên R2. Một cặp
``(user_id, exercise_id)`` có thể có nhiều phiên chat khác nhau — mỗi lần học
viên mở một cuộc trò chuyện mới sẽ tạo thêm một phiên (không ghi đè phiên cũ).

Object JSON có key
``chat_histories/<created_at>_<user_id>_<exercise_id>.json``::

    {
      "user_id": int,
      "exercise_id": int,
      "exercise_name": str,
      "created_at": ISO-8601 str,
      "updated_at": ISO-8601 str,
      "messages": [{"role": "user"|"assistant", "content": str}, ...]
    }

Bảng ``historychat`` lưu metadata (user_id, exercise_id, created_at,
modified_at) cùng ``path_storage`` chứa **key của object R2** tương ứng. ``id``
của row chính là ``session_id`` định danh phiên chat.
"""

import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.database import HistoryChat
from utils import r2_client

_LOCK = threading.Lock()

# Giới hạn số tin nhắn tối đa được giữ trong một phiên chat. Khi vượt quá,
# các tin nhắn cũ nhất sẽ bị cắt bớt, chỉ giữ lại MAX_MESSAGES tin gần nhất.
MAX_MESSAGES = 200


def _object_key(created_at: datetime, user_id: int, exercise_id: int) -> str:
    """Key của object JSON phiên chat trên R2.

    Key = ``chat_histories/<created_at>_<user_id>_<exercise_id>.json`` với
    ``created_at`` rút gọn còn ``YYYYMMDDHHMMSSffffff`` để mỗi phiên có một
    object riêng, không bị trùng.
    """
    ts = created_at.strftime("%Y%m%d%H%M%S%f")
    return (
        Path("chat_histories") / f"{ts}_{user_id}_{exercise_id}.json"
    ).as_posix()


def save_chat(
    session: Session,
    learner_id: int,
    exercise_id: int,
    exercise_name: str,
    messages: list[dict],
    session_id: int | None = None,
) -> int:
    """Lưu (hoặc cập nhật) toàn bộ tin nhắn của một phiên chat.

    - ``session_id is None`` → **tạo phiên mới**: thêm một row mới trong
      ``historychat`` và một file JSON mới.
    - ``session_id`` hợp lệ (thuộc đúng learner + exercise) → **tiếp tục phiên
      cũ**: ghi đè file JSON của phiên đó với toàn bộ messages mới và cập nhật
      ``modified_at``.

    Trả về ``session_id`` (id của row ``historychat``) để client dùng cho các
    lượt chat tiếp theo trong cùng cuộc trò chuyện.
    """
    if len(messages) > MAX_MESSAGES:
        messages = messages[-MAX_MESSAGES:]

    now = datetime.now(timezone.utc)

    record: HistoryChat | None = None
    if session_id is not None:
        record = session.exec(
            select(HistoryChat).where(
                HistoryChat.id == session_id,
                HistoryChat.user_id == learner_id,
                HistoryChat.exercise_id == exercise_id,
            )
        ).first()

    if record is None:
        # Phiên mới: tạo row trước để chốt created_at + path_storage (key R2).
        object_key = _object_key(now, learner_id, exercise_id)
        record = HistoryChat(
            user_id=learner_id,
            exercise_id=exercise_id,
            path_storage=object_key,
            created_at=now,
            modified_at=now,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        created_at = now
    else:
        object_key = record.path_storage
        created_at = record.created_at or now

    with _LOCK:
        existing = r2_client.get_json(object_key)
        created_at_iso = existing.get("created_at") or created_at.isoformat()
        r2_client.put_json(
            object_key,
            {
                "user_id": learner_id,
                "exercise_id": exercise_id,
                "exercise_name": exercise_name,
                "created_at": created_at_iso,
                "updated_at": now.isoformat(),
                "messages": messages,
            },
        )

    record.modified_at = now
    session.add(record)
    session.commit()
    return record.id


def get_sessions(
    session: Session, learner_id: int, exercise_id: int
) -> list[dict]:
    """Danh sách tóm tắt các phiên chat của learner trong **một exercise**.

    Lọc theo cả ``user_id`` và ``exercise_id`` (mỗi exercise chỉ thấy lịch sử
    chat của chính nó), sắp xếp giảm dần theo ``modified_at`` (phiên cập nhật
    gần nhất lên đầu).
    """
    records = session.exec(
        select(HistoryChat)
        .where(
            HistoryChat.user_id == learner_id,
            HistoryChat.exercise_id == exercise_id,
        )
        .order_by(HistoryChat.modified_at.desc())
    ).all()

    sessions: list[dict] = []
    for record in records:
        info = r2_client.get_json(record.path_storage)
        sessions.append(
            {
                "session_id": record.id,
                "exercise_id": record.exercise_id,
                "exercise_name": info.get("exercise_name", ""),
                "created_at": record.created_at.isoformat()
                if record.created_at
                else None,
                "updated_at": record.modified_at.isoformat()
                if record.modified_at
                else None,
                "message_count": len(info.get("messages", [])),
            }
        )
    return sessions


def get_session_detail(session: Session, session_id: int) -> dict | None:
    """Lấy thông tin đầy đủ của một phiên chat theo ``session_id``.

    Trả về dict ``{session_id, user_id, exercise_id, exercise_name, messages}``
    hoặc ``None`` nếu phiên không tồn tại.
    """
    record = session.exec(
        select(HistoryChat).where(HistoryChat.id == session_id)
    ).first()
    if record is None:
        return None
    info = r2_client.get_json(record.path_storage)
    return {
        "session_id": record.id,
        "user_id": record.user_id,
        "exercise_id": record.exercise_id,
        "exercise_name": info.get("exercise_name", ""),
        "messages": info.get("messages", []),
    }


def delete_session(session: Session, session_id: int) -> bool:
    """Xóa một phiên chat theo ``session_id`` (cả bản ghi DB lẫn object R2).

    Trả về ``True`` nếu xóa thành công, ``False`` nếu phiên không tồn tại.
    """
    record = session.exec(
        select(HistoryChat).where(HistoryChat.id == session_id)
    ).first()
    if record is None:
        return False

    with _LOCK:
        r2_client.delete_object(record.path_storage)

    session.delete(record)
    session.commit()
    return True
