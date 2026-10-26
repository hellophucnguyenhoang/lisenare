from datetime import datetime, timedelta, timezone
import io
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import (
    Brick,
    BrickInteraction,
    BrickMemory,
    BrickReaction,
    BrickReport,
    BrickReview,
    Island,
    Learner,
    LearnerSetting,
    Taggable,
    engine,
)
from main import app
from services import auth_service


def test_create_brick_with_tags_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 10"
            )
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Hello world unique test brick",
        "island_id": col_id,
        "tags": ["greeting", "basic"],
    }
    audio_file = io.BytesIO(b"fake audio data")

    with (
        patch(
            "utils.file_utils.save_upload_file",
            return_value=("mock/path.wav", None),
        ),
        patch("services.search_service.add_brick_embedding"),
    ):
        response = client.post(
            "/api/bricks",
            data={"json_data": json.dumps(brick_payload)},
            files={
                "target_audio_file": ("audio.wav", audio_file, "audio/wav")
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["native_text"] == "Xin chào"
    assert data["target_text"] == "Hello world unique test brick"
    assert data["target_lang"] == "en"
    assert data["island_id"] == col.id
    assert sorted(data["tags"]) == ["basic", "greeting"]
    brick_id = data["id"]

    # Verify Taggable records exist in DB
    with Session(engine) as session:
        taggables = session.exec(
            select(Taggable).where(
                Taggable.taggable_id == brick_id,
                Taggable.taggable_type == "Brick",
            )
        ).all()
        assert len(taggables) == 2

    # Update tags and target_lang
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )
    update_payload = {"tags": ["advanced", "phrases"], "target_lang": "ja"}
    with patch(
        "utils.file_utils.save_upload_file",
        return_value=("mock/path.wav", None),
    ):
        patch_response = client.patch(
            f"/api/bricks/{brick_id}",
            data={"json_data": json.dumps(update_payload)},
        )
    assert patch_response.status_code == 200
    updated_data = patch_response.json()
    assert sorted(updated_data["tags"]) == ["advanced", "phrases"]
    assert updated_data["target_lang"] == "ja"

    # Delete brick and verify taggables are removed
    with patch("services.search_service.remove_brick_embedding"):
        del_response = client.delete(f"/api/bricks/{brick_id}")
    assert del_response.status_code == 204

    with Session(engine) as session:
        taggables_after = session.exec(
            select(Taggable).where(
                Taggable.taggable_id == brick_id,
                Taggable.taggable_type == "Brick",
            )
        ).all()
        assert len(taggables_after) == 0

        brick_in_db = session.get(Brick, brick_id)
        assert brick_in_db is None

    app.dependency_overrides.clear()


def test_create_brick_with_custom_target_lang(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 10"
            )
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Konnichiwa",
        "target_lang": "ja",
        "island_id": col_id,
    }
    audio_file = io.BytesIO(b"fake audio data")

    with (
        patch(
            "utils.file_utils.save_upload_file",
            return_value=("mock/path_ja.wav", None),
        ),
        patch("services.search_service.add_brick_embedding"),
    ):
        response = client.post(
            "/api/bricks",
            data={"json_data": json.dumps(brick_payload)},
            files={
                "target_audio_file": ("audio.wav", audio_file, "audio/wav")
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["target_lang"] == "ja"
    brick_id = data["id"]

    with patch("services.search_service.remove_brick_embedding"):
        del_response = client.delete(f"/api/bricks/{brick_id}")
    assert del_response.status_code == 204

    app.dependency_overrides.clear()


def test_create_brick_island_not_found(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Test not found",
        "island_id": 999999,
    }
    audio_file = io.BytesIO(b"fake audio data")

    with patch(
        "utils.file_utils.save_upload_file",
        return_value=("mock/path.wav", None),
    ):
        response = client.post(
            "/api/bricks",
            data={"json_data": json.dumps(brick_payload)},
            files={
                "target_audio_file": ("audio.wav", audio_file, "audio/wav")
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 404


def test_create_brick_island_forbidden(client: TestClient):
    other_learner = Learner(id=99999, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 10"
            )
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Test forbidden",
        "island_id": col_id,
    }
    audio_file = io.BytesIO(b"fake audio data")

    with patch(
        "utils.file_utils.save_upload_file",
        return_value=("mock/path.wav", None),
    ):
        response = client.post(
            "/api/bricks",
            data={"json_data": json.dumps(brick_payload)},
            files={
                "target_audio_file": ("audio.wav", audio_file, "audio/wav")
            },
        )

    app.dependency_overrides.clear()
    assert response.status_code == 403


def test_forced_align_with_brick_success(client: TestClient):
    with Session(engine) as session:
        brick = session.exec(select(Brick)).first()
        assert brick is not None
        brick_id = brick.id
        creator_id = brick.creator_id
        target_text = brick.target_text

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "segments": [
            {"word": "hello", "start_sec": 0.1, "end_sec": 0.5},
            {"word": "world", "start_sec": 0.6, "end_sec": 1.0},
        ]
    }

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    learner = Learner(id=creator_id, name="Test Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("http_client.get_client", return_value=mock_client),
            patch(
                "services.audio_cache_service.get_brick_audio_url",
                return_value="http://test/audio.wav",
            ),
        ):
            response = client.get(f"/api/audio/forced-alignment/{brick_id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["word"] == "hello"
        assert data[0]["start_sec"] == 0.1
        assert data[0]["end_sec"] == 0.5

        mock_client.post.assert_called_once()
        posted_payload = mock_client.post.call_args[1]["json"]
        assert posted_payload["transcript"] == target_text
        assert posted_payload["audio_url"] == "http://test/audio.wav"
    finally:
        app.dependency_overrides.clear()


def test_forced_align_brick_not_found(client: TestClient):
    learner = Learner(id=1, name="Test Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )
    try:
        response = client.get("/api/audio/forced-alignment/999999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_save_review_integrated_learning_card(client: TestClient):
    from database import BrickMemory, BrickReview
    from schemas import ReviewCreate
    from services import brick_review_service

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None

        review_create = ReviewCreate(
            brick_id=brick.id,
            rating=3,
            is_answer_revealed=False,
            first_score=0.9,
            learner_target_text=brick.target_text,
        )

        total_reviews = brick_review_service.save_review(
            session=session,
            learner_id=2,
            review_create=review_create,
        )

        assert isinstance(total_reviews, int)
        assert total_reviews >= 1

        # Verify BrickReview has fsrs_log_dict
        review = session.exec(
            select(BrickReview)
            .where(
                BrickReview.learner_id == 2, BrickReview.brick_id == brick.id
            )
            .order_by(BrickReview.reviewed_at.desc())
        ).first()
        assert review is not None
        assert review.fsrs_log_dict is not None
        assert "rating" in review.fsrs_log_dict

        # Verify BrickMemory was updated
        memory = session.exec(
            select(BrickMemory).where(
                BrickMemory.learner_id == 2,
                BrickMemory.brick_id == brick.id,
            )
        ).first()
        assert memory is not None
        assert memory.due is not None
        assert "stability" in memory.fsrs_card_dict

        # Cleanup review
        session.delete(review)
        session.commit()


def test_get_next_brick_with_brick_id_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None
        brick_id = brick.id
        brick_target_text = brick.target_text

    response = client.get(f"/api/bricks/next?brick_id={brick_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == brick_id
    assert data["target_text"] == brick_target_text
    assert "tags" in data


def test_get_next_brick_with_brick_id_not_found(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/api/bricks/next?brick_id=999999")
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_get_next_brick_with_brick_id_forbidden(client: TestClient):
    other_learner = Learner(id=99999, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None
        brick_id = brick.id

    response = client.get(f"/api/bricks/next?brick_id={brick_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_get_next_brick_without_brick_id(client: TestClient):
    existing_learner = Learner(
        id=2, setting=LearnerSetting(retrieval_lang="en")
    )
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/api/bricks/next")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["target_lang"] == "en"


def test_get_next_brick_filters_by_retrieval_lang(client: TestClient):
    learner_es = Learner(id=2, setting=LearnerSetting(retrieval_lang="es"))
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_es
    )

    response = client.get("/api/bricks/next")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() is None


def test_get_next_brick_with_specific_id_ignores_retrieval_lang(
    client: TestClient,
):
    with Session(engine) as session:
        brick_en = session.exec(
            select(Brick).where(
                Brick.creator_id == 2, Brick.target_lang == "en"
            )
        ).first()
        assert brick_en is not None
        brick_en_id = brick_en.id

    learner_ja = Learner(id=2, setting=LearnerSetting(retrieval_lang="ja"))
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_ja
    )

    response = client.get(f"/api/bricks/next?brick_id={brick_en_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == brick_en_id
    assert data["target_lang"] == "en"


def test_get_bricks_kind_and_tags_filter(client: TestClient):
    from services.tag_service import set_tags_for_entity

    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Island).where(Island.creator_id == 2)
        ).first()
        assert col is not None

        # Create 1 word brick with tag "test_tag_word"
        brick_word = Brick(
            native_text="Từ đơn",
            target_text="SingleWordTest",
            target_audio_path="fake/path.wav",
            target_lang="en",
            kind="word",
            is_private=True,
            island_id=col.id,
            creator_id=2,
        )
        session.add(brick_word)
        session.commit()
        session.refresh(brick_word)
        brick_word_id = brick_word.id
        set_tags_for_entity(
            session, brick_word_id, "Brick", ["test_tag_word"], 2
        )
        session.commit()

        # Create 1 sentence brick with tag "test_tag_sentence"
        brick_sent = Brick(
            native_text="Câu đầy đủ",
            target_text="FullSentenceTest",
            target_audio_path="fake/path.wav",
            target_lang="en",
            kind="sentence",
            is_private=True,
            island_id=col.id,
            creator_id=2,
        )
        session.add(brick_sent)
        session.commit()
        session.refresh(brick_sent)
        brick_sent_id = brick_sent.id
        set_tags_for_entity(
            session, brick_sent_id, "Brick", ["test_tag_sentence"], 2
        )
        session.commit()

    try:
        # Test kind filter = word
        resp_word = client.get("/api/bricks?kind=word")
        assert resp_word.status_code == 200
        data_word = resp_word.json()
        word_ids = [item["id"] for item in data_word["items"]]
        assert brick_word_id in word_ids
        assert brick_sent_id not in word_ids
        assert all(item["kind"] == "word" for item in data_word["items"])

        # Test kind filter = sentence
        resp_sent = client.get("/api/bricks?kind=sentence")
        assert resp_sent.status_code == 200
        data_sent = resp_sent.json()
        sent_ids = [item["id"] for item in data_sent["items"]]
        assert brick_sent_id in sent_ids
        assert brick_word_id not in sent_ids
        assert all(item["kind"] == "sentence" for item in data_sent["items"])

        # Test tags filter single tag
        resp_tag = client.get("/api/bricks?tags=test_tag_word")
        assert resp_tag.status_code == 200
        data_tag = resp_tag.json()
        tag_ids = [item["id"] for item in data_tag["items"]]
        assert brick_word_id in tag_ids
        assert brick_sent_id not in tag_ids

        # Test tags filter multiple tags (comma separated)
        resp_tags = client.get(
            "/api/bricks?tags=test_tag_word,test_tag_sentence"
        )
        assert resp_tags.status_code == 200
        data_tags = resp_tags.json()
        both_ids = [item["id"] for item in data_tags["items"]]
        assert brick_word_id in both_ids
        assert brick_sent_id in both_ids

        # Test combined kind and tags filter
        resp_combined = client.get(
            "/api/bricks?kind=word&tags=test_tag_sentence"
        )
        assert resp_combined.status_code == 200
        assert resp_combined.json()["total"] == 0

        # Test nonexistent tag
        resp_none = client.get("/api/bricks?tags=nonexistent_xyz")
        assert resp_none.status_code == 200
        assert resp_none.json()["total"] == 0
        assert resp_none.json()["items"] == []

    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            bw = session.get(Brick, brick_word_id)
            if bw:
                session.delete(bw)
            bs = session.get(Brick, brick_sent_id)
            if bs:
                session.delete(bs)
            session.commit()


def test_get_recommended_bricks_unauthenticated_fails(client: TestClient):
    response = client.get("/api/bricks/recommended/new_test_session_id")
    assert response.status_code == 401


def test_get_recommended_bricks_endpoint(client: TestClient):
    fake_learner = Learner(
        id=2, name="test_learner", setting=LearnerSetting(retrieval_lang="en")
    )
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )
    try:
        response = client.get("/api/bricks/recommended/new_test_session_id")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == data["total"]
        assert len(data["items"]) > 0
        for b in data["items"]:
            assert b["target_lang"] == "en"
    finally:
        app.dependency_overrides.clear()


def test_get_recommended_bricks_matches_retrieval_lang(client: TestClient):
    fake_learner = Learner(
        id=2,
        name="test_learner",
        setting=LearnerSetting(retrieval_lang="non_existent_lang"),
    )
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )
    try:
        response = client.get(
            "/api/bricks/recommended/test_session_lang_filter"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
    finally:
        app.dependency_overrides.clear()


def test_get_recommended_bricks_excludes_cached_recommended_items(
    client: TestClient,
):
    from redis_client import get_redis_client

    session_id = "test_redis_dedup_session"
    redis = get_redis_client()
    cache_key = f"recommended_bricks:{session_id}"
    redis.delete(cache_key)

    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )
    try:
        # First call: receives 5 bricks and caches their IDs in redis
        resp1 = client.get(f"/api/bricks/recommended/{session_id}")
        assert resp1.status_code == 200
        items1 = resp1.json()["items"]
        ids1 = {item["id"] for item in items1}

        # Verify redis cache contains the recommended brick IDs
        cached = {int(bid) for bid in redis.smembers(cache_key)}
        assert ids1.issubset(cached)

        # Second call without user interaction: must not re-recommend the same 5 bricks
        resp2 = client.get(f"/api/bricks/recommended/{session_id}")
        assert resp2.status_code == 200
        items2 = resp2.json()["items"]
        ids2 = {item["id"] for item in items2}

        # The two sets of recommended brick IDs should be completely disjoint
        assert ids1.isdisjoint(ids2)
    finally:
        redis.delete(cache_key)
        app.dependency_overrides.clear()


def test_report_brick_success(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with Session(engine) as session:
        brick = session.exec(select(Brick)).first()
        assert brick is not None
        brick_id = brick.id

    try:
        response = client.post(
            f"/api/bricks/{brick_id}/report",
            json={"reason": "Inaccurate translation or audio glitch"},
        )
        assert response.status_code == 201

        with Session(engine) as session:
            report = session.exec(
                select(BrickReport).where(
                    BrickReport.brick_id == brick_id,
                    BrickReport.learner_id == 2,
                    BrickReport.reason
                    == "Inaccurate translation or audio glitch",
                )
            ).first()
            assert report is not None
            assert report.status == "open"
    finally:
        app.dependency_overrides.clear()


def test_report_brick_not_found(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    try:
        response = client.post(
            "/api/bricks/99999999/report",
            json={"reason": "Does not exist"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_next_brick_excludes_reported_brick(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with Session(engine) as session:
        # Create a report for a brick owned by learner 2
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None
        brick_id = brick.id

        report = BrickReport(
            brick_id=brick_id,
            learner_id=2,
            reason="Corrupted audio",
            status="open",
        )
        session.add(report)
        session.commit()
        report_id = report.id

    try:
        # Fetching next brick should never return the reported brick
        for _ in range(5):
            response = client.get("/api/bricks/next")
            assert response.status_code == 200
            data = response.json()
            if data is not None:
                assert data["id"] != brick_id
    finally:
        with Session(engine) as session:
            r = session.get(BrickReport, report_id)
            if r:
                session.delete(r)
                session.commit()
        app.dependency_overrides.clear()


def test_forget_brick_success(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None
        brick_id = brick.id

        # Seed memory, review, reaction, and interaction for this brick
        memory = session.exec(
            select(BrickMemory).where(
                BrickMemory.brick_id == brick_id,
                BrickMemory.learner_id == 2,
            )
        ).first()
        if not memory:
            memory = BrickMemory(
                brick_id=brick_id,
                learner_id=2,
                due=brick.last_edit_at,
            )
            session.add(memory)

        review = BrickReview(
            brick_id=brick_id,
            learner_id=2,
            first_score=1.0,
            fsrs_rating=3,
        )
        session.add(review)

        reaction = session.get(BrickReaction, (2, brick_id))
        if not reaction:
            reaction = BrickReaction(
                learner_id=2,
                brick_id=brick_id,
                reaction="LIKE",
            )
            session.add(reaction)

        interaction = BrickInteraction(
            brick_id=brick_id,
            learner_id=2,
            session_id="test_forget_session",
            type="LISTEN",
        )
        session.add(interaction)
        session.commit()

    try:
        response = client.post(f"/api/bricks/{brick_id}/forget")
        assert response.status_code == 204

        with Session(engine) as session:
            # Brick still exists
            remaining_brick = session.get(Brick, brick_id)
            assert remaining_brick is not None

            # Memory is removed
            rem = session.exec(
                select(BrickMemory).where(
                    BrickMemory.brick_id == brick_id,
                    BrickMemory.learner_id == 2,
                )
            ).first()
            assert rem is None

            # Reviews are removed
            revs = session.exec(
                select(BrickReview).where(
                    BrickReview.brick_id == brick_id,
                    BrickReview.learner_id == 2,
                )
            ).all()
            assert len(revs) == 0

            # Reaction is removed
            react = session.get(BrickReaction, (2, brick_id))
            assert react is None

            # Interactions are removed
            ints = session.exec(
                select(BrickInteraction).where(
                    BrickInteraction.brick_id == brick_id,
                    BrickInteraction.learner_id == 2,
                )
            ).all()
            assert len(ints) == 0
    finally:
        app.dependency_overrides.clear()


def test_forget_brick_not_found(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    try:
        response = client.post("/api/bricks/99999999/forget")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_skip_brick_success(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(
                Brick.creator_id == 2,
                Brick.is_skipped == False,  # noqa: E712
            )
        ).first()
        assert brick is not None
        brick_id = brick.id

    try:
        response = client.post(f"/api/bricks/{brick_id}/skip")
        assert response.status_code == 204

        with Session(engine) as session:
            refreshed = session.get(Brick, brick_id)
            assert refreshed.is_skipped is True

        # Check get_bricks with status=SKIPPED
        skipped_resp = client.get("/api/bricks?status=SKIPPED")
        assert skipped_resp.status_code == 200
        data = skipped_resp.json()
        matching_ids = [item["id"] for item in data["items"]]
        assert brick_id in matching_ids

        # Check lowercase status=skipped also works
        skipped_lower_resp = client.get("/api/bricks?status=skipped")
        assert skipped_lower_resp.status_code == 200

        # Check get_bricks with status=NOT_LEARNED does not include skipped brick
        not_learned_resp = client.get("/api/bricks?status=NOT_LEARNED")
        assert not_learned_resp.status_code == 200
        not_learned_ids = [
            item["id"] for item in not_learned_resp.json()["items"]
        ]
        assert brick_id not in not_learned_ids

        # Check get_next_brick with explicit brick_id returns None for skipped brick
        next_resp = client.get(f"/api/bricks/next?brick_id={brick_id}")
        assert next_resp.status_code == 200
        assert next_resp.json() is None
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            b = session.get(Brick, brick_id)
            if b:
                b.is_skipped = False
                session.add(b)
                session.commit()


def test_skip_brick_forbidden(client: TestClient):
    other_learner = Learner(id=99999, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    with Session(engine) as session:
        brick = session.exec(
            select(Brick).where(Brick.creator_id == 2)
        ).first()
        assert brick is not None
        brick_id = brick.id

    try:
        response = client.post(f"/api/bricks/{brick_id}/skip")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_skip_brick_not_found(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    try:
        response = client.post("/api/bricks/99999999/skip")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_next_brick_skips_skipped_bricks(client: TestClient):
    learner_id = 555
    created_brick_ids = []
    island_id = None
    with Session(engine) as session:
        learner = session.get(Learner, learner_id)
        if not learner:
            learner = Learner(
                id=learner_id,
                name="SkipTestLearner",
                setting=LearnerSetting(retrieval_lang="en"),
            )
            session.add(learner)

        island = Island(name="SkipTestIsland", creator_id=learner_id)
        session.add(island)
        session.flush()
        island_id = island.id

        b_skipped = Brick(
            native_text="N_skipped",
            target_text="A",  # Shorter, would normally be chosen first
            target_audio_path="p1",
            target_lang="en",
            kind="word",
            is_private=True,
            is_skipped=True,
            creator_id=learner_id,
            island_id=island.id,
        )
        b_normal = Brick(
            native_text="N_normal",
            target_text="Normal Target",
            target_audio_path="p2",
            target_lang="en",
            kind="word",
            is_private=True,
            is_skipped=False,
            creator_id=learner_id,
            island_id=island.id,
        )
        session.add(b_skipped)
        session.add(b_normal)
        session.commit()
        created_brick_ids = [b_skipped.id, b_normal.id]

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=learner_id, setting=LearnerSetting(retrieval_lang="en"))
    )
    try:
        response = client.get(f"/api/bricks/next?island_ids={island_id}")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["id"] == b_normal.id
        assert data["target_text"] == "Normal Target"
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            for bid in created_brick_ids:
                b = session.get(Brick, bid)
                if b:
                    session.delete(b)
            if island_id:
                isl = session.get(Island, island_id)
                if isl:
                    session.delete(isl)
            lrn = session.get(Learner, learner_id)
            if lrn:
                session.delete(lrn)
            session.commit()


def test_get_listening_bricks_returns_full_audio_url(client: TestClient):
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with patch(
        "services.audio_cache_service.get_brick_audio_url",
        return_value="https://cdn.example.com/audio/brick_audio.wav",
    ) as mock_get_audio:
        try:
            response = client.get("/api/bricks/listening?limit=5")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) > 0
            for item in data["items"]:
                assert (
                    item["audio_path"]
                    == "https://cdn.example.com/audio/brick_audio.wav"
                )
                assert "target_pron" in item
                assert "context" in item
            assert mock_get_audio.called
        finally:
            app.dependency_overrides.clear()


def test_get_next_brick_prefers_shared_tags(client: TestClient):
    learner_id = 501
    with Session(engine) as session:
        learner = session.get(Learner, learner_id)
        if not learner:
            learner = Learner(
                id=learner_id,
                name="TagLearner",
                setting=LearnerSetting(retrieval_lang="en"),
            )
            session.add(learner)

        island = Island(name="TagIsland", creator_id=learner_id)
        session.add(island)
        session.flush()

        b1 = Brick(
            native_text="N1",
            target_text="Shared Tag Learned Brick",
            target_audio_path="p1",
            target_lang="en",
            kind="word",
            is_private=True,
            creator_id=learner_id,
            island_id=island.id,
        )
        b2 = Brick(
            native_text="N2",
            target_text="Shared Tag Unlearned Brick",
            target_audio_path="p2",
            target_lang="en",
            kind="word",
            is_private=True,
            creator_id=learner_id,
            island_id=island.id,
        )
        b3 = Brick(
            native_text="N3",
            target_text="Different Tag Brick",
            target_audio_path="p3",
            target_lang="en",
            kind="word",
            is_private=True,
            creator_id=learner_id,
            island_id=island.id,
        )
        session.add_all([b1, b2, b3])
        session.flush()

        from services.tag_service import set_tags_for_entity

        set_tags_for_entity(session, b1.id, "Brick", ["commontag"], learner_id)
        set_tags_for_entity(session, b2.id, "Brick", ["commontag"], learner_id)
        set_tags_for_entity(session, b3.id, "Brick", ["uniquetag"], learner_id)

        # Mark b1 as learned in BrickMemory with future due date (so it's not due for review)
        mem = BrickMemory(
            learner_id=learner_id,
            brick_id=b1.id,
            due=datetime.now(timezone.utc) + timedelta(days=5),
        )
        session.add(mem)
        session.commit()
        b2_id = b2.id
        created_brick_ids = [b1.id, b2.id, b3.id]
        island_id = island.id

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=learner_id, setting=LearnerSetting(retrieval_lang="en"))
    )
    try:
        response = client.get("/api/bricks/next")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        # It must prefer b2 because b2 shares 'commontag' with learned b1
        assert data["id"] == b2_id
        assert "commontag" in data["tags"]
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            for bid in created_brick_ids:
                b = session.get(Brick, bid)
                if b:
                    session.delete(b)
            isl = session.get(Island, island_id)
            if isl:
                session.delete(isl)
            lrn = session.get(Learner, learner_id)
            if lrn:
                session.delete(lrn)
            session.commit()


def test_get_next_brick_prefers_shorter_target_text_when_no_shared_tags(
    client: TestClient,
):
    learner_id = 502
    created_brick_ids = []
    island_id = None
    with Session(engine) as session:
        learner = session.get(Learner, learner_id)
        if not learner:
            learner = Learner(
                id=learner_id,
                name="ShortLearner",
                setting=LearnerSetting(retrieval_lang="en"),
            )
            session.add(learner)

        island = Island(name="ShortIsland", creator_id=learner_id)
        session.add(island)
        session.flush()
        island_id = island.id

        # Add 1 very short brick and 15 long bricks
        short_brick = Brick(
            native_text="N_short",
            target_text="Hi",
            target_audio_path="p_short",
            target_lang="en",
            kind="word",
            is_private=True,
            creator_id=learner_id,
            island_id=island.id,
        )
        session.add(short_brick)
        session.flush()
        created_brick_ids.append(short_brick.id)

        for i in range(15):
            long_brick = Brick(
                native_text=f"N_long_{i}",
                target_text=f"This is an exceptionally long and complicated sentence number {i} designed to test length preference",
                target_audio_path=f"p_long_{i}",
                target_lang="en",
                kind="sentence",
                is_private=True,
                creator_id=learner_id,
                island_id=island.id,
            )
            session.add(long_brick)
            session.flush()
            created_brick_ids.append(long_brick.id)

        session.commit()
        short_brick_id = short_brick.id

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        Learner(id=learner_id, setting=LearnerSetting(retrieval_lang="en"))
    )
    try:
        response = client.get("/api/bricks/next")
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["id"] == short_brick_id
        assert data["target_text"] == "Hi"
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            for bid in created_brick_ids:
                b = session.get(Brick, bid)
                if b:
                    session.delete(b)
            if island_id:
                isl = session.get(Island, island_id)
                if isl:
                    session.delete(isl)
            lrn = session.get(Learner, learner_id)
            if lrn:
                session.delete(lrn)
            session.commit()
