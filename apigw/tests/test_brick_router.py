import io
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import (
    Brick,
    Collection,
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
            select(Collection).where(Collection.creator_id == 2)
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Hello world unique test brick",
        "collection_id": col_id,
        "tags": ["greeting", "basic"],
    }
    audio_file = io.BytesIO(b"fake audio data")

    with (
        patch(
            "utils.file_utils.save_upload_file",
            return_value=("mock/path.wav", None),
        ),
        patch("services.context_search_service.add_item_to_vector_store"),
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
    assert data["collection_id"] == col.id
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
    with patch(
        "services.context_search_service.delete_item_from_vector_store"
    ):
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
            select(Collection).where(Collection.creator_id == 2)
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Konnichiwa",
        "target_lang": "ja",
        "collection_id": col_id,
    }
    audio_file = io.BytesIO(b"fake audio data")

    with (
        patch(
            "utils.file_utils.save_upload_file",
            return_value=("mock/path_ja.wav", None),
        ),
        patch("services.context_search_service.add_item_to_vector_store"),
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

    with patch(
        "services.context_search_service.delete_item_from_vector_store"
    ):
        del_response = client.delete(f"/api/bricks/{brick_id}")
    assert del_response.status_code == 204

    app.dependency_overrides.clear()


def test_create_brick_collection_not_found(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Test not found",
        "collection_id": 999999,
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


def test_create_brick_collection_forbidden(client: TestClient):
    other_learner = Learner(id=99999, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Collection).where(Collection.creator_id == 2)
        ).first()
        assert col is not None
        col_id = col.id

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Test forbidden",
        "collection_id": col_id,
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
        id=2, setting=LearnerSetting(practice_lang="en")
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


def test_get_next_brick_filters_by_practice_lang(client: TestClient):
    learner_ja = Learner(id=2, setting=LearnerSetting(practice_lang="ja"))
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_ja
    )

    response = client.get("/api/bricks/next")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() is None


def test_get_next_brick_with_specific_id_ignores_practice_lang(
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

    learner_ja = Learner(id=2, setting=LearnerSetting(practice_lang="ja"))
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
            select(Collection).where(Collection.creator_id == 2)
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
            collection_id=col.id,
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
            collection_id=col.id,
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
    fake_learner = Learner(id=2, name="test_learner", setting=LearnerSetting())
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
    finally:
        app.dependency_overrides.clear()
