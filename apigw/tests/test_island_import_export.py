from datetime import datetime, timezone
import io
import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import (
    Brick,
    BrickMemory,
    BrickReview,
    Island,
    Learner,
    LearnerSetting,
    engine,
)
from main import app
from services import auth_service
from services.tag_service import set_tags_for_entity


def _ensure_learner(session: Session, learner_id: int, name: str) -> Learner:
    learner = session.get(Learner, learner_id)
    if not learner:
        learner = Learner(id=learner_id, name=name, setting=LearnerSetting())
        session.add(learner)
        session.commit()
        session.refresh(learner)
    return learner


def _ensure_island(session: Session, creator_id: int, name: str) -> Island:
    col = session.exec(
        select(Island).where(
            Island.creator_id == creator_id, Island.name == name
        )
    ).first()
    if not col:
        col = Island(name=name, creator_id=creator_id)
        session.add(col)
        session.commit()
        session.refresh(col)
    return col


def test_export_island_success(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 101, "Exporter")
        col = _ensure_island(session, 101, f"Col-Export-{suffix}")

        b1 = Brick(
            native_text="Xin chào",
            target_text=f"Hello-{suffix}",
            target_audio_path=f"audios/hello-{suffix}.wav",
            kind="word",
            is_private=True,
            creator_id=101,
            island_id=col.id,
        )
        b2 = Brick(
            native_text="Tạm biệt",
            target_text=f"Goodbye-{suffix}",
            target_audio_path=f"audios/goodbye-{suffix}.wav",
            kind="sentence",
            is_private=False,
            creator_id=101,
            island_id=col.id,
        )
        session.add(b1)
        session.add(b2)
        session.commit()
        session.refresh(b1)
        session.refresh(b2)

        set_tags_for_entity(
            session, b1.id, "Brick", ["greeting", "basic"], 101
        )
        session.commit()
        col_id = col.id

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=101, name="Exporter", setting=LearnerSetting())
    )
    try:
        response = client.get(f"/api/islands/{col_id}/export")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify independence of fields
        texts = [item["target_text"] for item in data]
        assert f"Hello-{suffix}" in texts
        assert f"Goodbye-{suffix}" in texts

        # Verify no learner-specific or DB-specific ID fields
        for item in data:
            assert "id" not in item or item.get("id") is None
            assert "creator_id" not in item
            assert "island_id" not in item
            assert "target_audio_path" in item

        # Verify tags exported
        b1_item = next(
            i for i in data if i["target_text"] == f"Hello-{suffix}"
        )
        assert sorted(b1_item["tags"]) == ["basic", "greeting"]
    finally:
        app.dependency_overrides.clear()


def test_export_other_learner_island_only_returns_public(
    client: TestClient,
):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 102, "Owner")
        _ensure_learner(session, 103, "Other Learner")
        col = _ensure_island(session, 102, f"Col-Mixed-{suffix}")

        b_priv = Brick(
            native_text="Bí mật",
            target_text=f"Secret-{suffix}",
            target_audio_path=f"audios/secret-{suffix}.wav",
            kind="sentence",
            is_private=True,
            creator_id=102,
            island_id=col.id,
        )
        b_pub = Brick(
            native_text="Công khai",
            target_text=f"Public-{suffix}",
            target_audio_path=f"audios/public-{suffix}.wav",
            kind="sentence",
            is_private=False,
            creator_id=102,
            island_id=col.id,
        )
        session.add(b_priv)
        session.add(b_pub)
        session.commit()
        col_id = col.id

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=103, name="Other Learner", setting=LearnerSetting())
    )
    try:
        response = client.get(f"/api/islands/{col_id}/export")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target_text"] == f"Public-{suffix}"
    finally:
        app.dependency_overrides.clear()


def test_export_island_not_found(client: TestClient):
    with Session(engine) as session:
        _ensure_learner(session, 101, "Exporter")

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=101, name="Exporter", setting=LearnerSetting())
    )
    try:
        response = client.get("/api/islands/999999/export")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_import_island_success(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 104, "Importer")
        target_col = _ensure_island(session, 104, f"Target-Col-{suffix}")
        target_col_id = target_col.id

    import_data = [
        {
            "native_text": "Táo",
            "target_text": f"Apple-{suffix}",
            "target_audio_path": f"audios/apple-{suffix}.wav",
            "kind": "word",
            "tags": ["fruit", "food"],
        },
        {
            "native_text": "Chuối",
            "target_text": f"Banana-{suffix}",
            "target_audio_path": f"audios/banana-{suffix}.wav",
            "kind": "word",
            "tags": ["fruit"],
        },
    ]

    file_bytes = io.BytesIO(json.dumps(import_data).encode("utf-8"))

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=104, name="Importer", setting=LearnerSetting())
    )
    try:
        response = client.post(
            f"/api/islands/{target_col_id}/import",
            files={"file": ("bricks.json", file_bytes, "application/json")},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["added"] == 2
        assert result["skipped"] == 0

        # Verify bricks created in database for the importer
        with Session(engine) as session:
            imported = session.exec(
                select(Brick).where(Brick.island_id == target_col_id)
            ).all()
            assert len(imported) == 2
            for b in imported:
                assert b.creator_id == 104
                assert b.island_id == target_col_id

        # Verify duplicate import skips existing
        file_bytes.seek(0)
        dup_response = client.post(
            f"/api/islands/{target_col_id}/import",
            files={"file": ("bricks.json", file_bytes, "application/json")},
        )
        assert dup_response.status_code == 200
        dup_result = dup_response.json()
        assert dup_result["added"] == 0
        assert dup_result["skipped"] == 2
    finally:
        app.dependency_overrides.clear()


def test_import_island_wrapped_in_dict(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 105, "Importer Dict")
        target_col = _ensure_island(session, 105, f"Dict-Col-{suffix}")
        target_col_id = target_col.id

    import_data = {
        "bricks": [
            {
                "native_text": "Mặt trời",
                "target_text": f"Sun-{suffix}",
                "target_audio_path": f"audios/sun-{suffix}.wav",
                "kind": "word",
            }
        ]
    }

    file_bytes = io.BytesIO(json.dumps(import_data).encode("utf-8"))

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=105, name="Importer Dict", setting=LearnerSetting())
    )
    try:
        response = client.post(
            f"/api/islands/{target_col_id}/import",
            files={"file": ("bricks.json", file_bytes, "application/json")},
        )
        assert response.status_code == 200
        assert response.json()["added"] == 1
    finally:
        app.dependency_overrides.clear()


def test_import_island_forbidden_to_other_learner(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 106, "Owner Learner")
        _ensure_learner(session, 107, "Attacker Learner")
        col = _ensure_island(session, 106, f"Owner-Col-{suffix}")
        col_id = col.id

    import_data = [
        {
            "native_text": "Hack",
            "target_text": f"Hack-{suffix}",
            "target_audio_path": "audios/hack.wav",
        }
    ]
    file_bytes = io.BytesIO(json.dumps(import_data).encode("utf-8"))

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=107, name="Attacker Learner", setting=LearnerSetting())
    )
    try:
        response = client.post(
            f"/api/islands/{col_id}/import",
            files={"file": ("hack.json", file_bytes, "application/json")},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_import_island_invalid_json(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        _ensure_learner(session, 108, "JSON Tester")
        col = _ensure_island(session, 108, f"Invalid-Col-{suffix}")
        col_id = col.id

    bad_bytes = io.BytesIO(b"this is not json {")

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=108, name="JSON Tester", setting=LearnerSetting())
    )
    try:
        response = client.post(
            f"/api/islands/{col_id}/import",
            files={"file": ("bad.json", bad_bytes, "application/json")},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_export_island_with_memory_and_reviews(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        _ensure_learner(session, 109, "MemExporter")
        col = _ensure_island(session, 109, f"MemCol-{suffix}")

        b = Brick(
            native_text="Kỷ niệm",
            target_text=f"Memory-{suffix}",
            target_audio_path=f"audios/mem-{suffix}.wav",
            kind="word",
            is_private=True,
            creator_id=109,
            island_id=col.id,
        )
        session.add(b)
        session.commit()
        session.refresh(b)

        mem = BrickMemory(
            learner_id=109,
            brick_id=b.id,
            fsrs_card_dict={"state": 2, "stability": 4.5},
            due=now,
        )
        rev = BrickReview(
            learner_id=109,
            brick_id=b.id,
            reviewed_at=now,
            first_score=0.95,
            is_answer_revealed=False,
            fsrs_rating=3,
            fsrs_log_dict={"rating": 3},
            learner_target_text=f"Memory-{suffix}",
        )
        session.add(mem)
        session.add(rev)
        session.commit()
        col_id = col.id

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=109, name="MemExporter", setting=LearnerSetting())
    )
    try:
        # Default: both True
        res_default = client.get(f"/api/islands/{col_id}/export")
        assert res_default.status_code == 200
        data_default = res_default.json()
        assert len(data_default) == 1
        item = data_default[0]
        assert item["memory"] is not None
        assert item["memory"]["fsrs_card_dict"] == {
            "state": 2,
            "stability": 4.5,
        }
        assert len(item["review_history"]) == 1
        assert item["review_history"][0]["first_score"] == 0.95

        # include_memory=False
        res_no_mem = client.get(
            f"/api/islands/{col_id}/export?include_memory=false"
        )
        assert res_no_mem.status_code == 200
        data_no_mem = res_no_mem.json()
        assert data_no_mem[0]["memory"] is None
        assert data_no_mem[0]["review_history"] is not None

        # include_review_history=False
        res_no_rev = client.get(
            f"/api/islands/{col_id}/export?include_review_history=false"
        )
        assert res_no_rev.status_code == 200
        data_no_rev = res_no_rev.json()
        assert data_no_rev[0]["memory"] is not None
        assert data_no_rev[0]["review_history"] is None

        # Both False
        res_none = client.get(
            f"/api/islands/{col_id}/export?include_memory=false&include_review_history=false"
        )
        assert res_none.status_code == 200
        data_none = res_none.json()
        assert data_none[0]["memory"] is None
        assert data_none[0]["review_history"] is None
    finally:
        app.dependency_overrides.clear()


def test_import_island_with_memory_and_reviews(client: TestClient):
    suffix = uuid.uuid4().hex[:6]
    now_iso = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        _ensure_learner(session, 110, "MemImporter")
        target_col = _ensure_island(session, 110, f"ImportCol-{suffix}")
        target_col_id = target_col.id

    import_data = [
        {
            "native_text": "Hồi tưởng",
            "target_text": f"Recall-{suffix}",
            "target_audio_path": f"audios/recall-{suffix}.wav",
            "kind": "word",
            "tags": ["history"],
            "memory": {
                "fsrs_card_dict": {"stability": 5.0},
                "due": now_iso,
            },
            "reviews": [
                {
                    "reviewed_at": now_iso,
                    "first_score": 1.0,
                    "is_answer_revealed": False,
                    "fsrs_rating": 4,
                    "fsrs_log_dict": {"rating": 4},
                }
            ],
        }
    ]

    file_bytes = io.BytesIO(json.dumps(import_data).encode("utf-8"))

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=110, name="MemImporter", setting=LearnerSetting())
    )
    try:
        response = client.post(
            f"/api/islands/{target_col_id}/import",
            files={"file": ("bricks.json", file_bytes, "application/json")},
        )
        assert response.status_code == 200
        assert response.json()["added"] == 1

        with Session(engine) as session:
            brick = session.exec(
                select(Brick).where(Brick.island_id == target_col_id)
            ).first()
            assert brick is not None

            # Verify BrickMemory created for importer
            mem = session.exec(
                select(BrickMemory).where(
                    BrickMemory.brick_id == brick.id,
                    BrickMemory.learner_id == 110,
                )
            ).first()
            assert mem is not None
            assert mem.fsrs_card_dict == {"stability": 5.0}

            # Verify BrickReview created for importer
            reviews = session.exec(
                select(BrickReview).where(
                    BrickReview.brick_id == brick.id,
                    BrickReview.learner_id == 110,
                )
            ).all()
            assert len(reviews) == 1
            assert reviews[0].first_score == 1.0
            assert reviews[0].fsrs_rating == 4
    finally:
        app.dependency_overrides.clear()
