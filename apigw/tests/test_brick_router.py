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
        patch("app.services.context_search_service.add_item_to_vector_store"),
    ):
        response = client.post(
            "/bricks",
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
            f"/bricks/{brick_id}",
            data={"json_data": json.dumps(update_payload)},
        )
    assert patch_response.status_code == 200
    updated_data = patch_response.json()
    assert sorted(updated_data["tags"]) == ["advanced", "phrases"]
    assert updated_data["target_lang"] == "ja"

    # Delete brick and verify taggables are removed
    with patch(
        "app.services.context_search_service.delete_item_from_vector_store"
    ):
        del_response = client.delete(f"/bricks/{brick_id}")
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
        patch("app.services.context_search_service.add_item_to_vector_store"),
    ):
        response = client.post(
            "/bricks",
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
        "app.services.context_search_service.delete_item_from_vector_store"
    ):
        del_response = client.delete(f"/bricks/{brick_id}")
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
            "/bricks",
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
            "/bricks",
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
        target_audio_path = brick.target_audio_path
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

    with patch("app.http_client.get_client", return_value=mock_client):
        response = client.get(f"/audio/forced-alignment/{target_audio_path}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["word"] == "hello"
    assert data[0]["start_sec"] == 0.1
    assert data[0]["end_sec"] == 0.5

    mock_client.post.assert_called_once()
    posted_payload = mock_client.post.call_args[1]["json"]
    assert posted_payload["transcript"] == target_text


def test_forced_align_brick_not_found(client: TestClient):
    response = client.get(
        "/audio/forced-alignment/non_existent/audio/path.wav"
    )
    assert response.status_code == 404


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

    response = client.get(f"/bricks/next?brick_id={brick_id}")
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

    response = client.get("/bricks/next?brick_id=999999")
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

    response = client.get(f"/bricks/next?brick_id={brick_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_get_next_brick_without_brick_id(client: TestClient):
    existing_learner = Learner(
        id=2, setting=LearnerSetting(practice_lang="en")
    )
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/bricks/next")
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

    response = client.get("/bricks/next")
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

    response = client.get(f"/bricks/next?brick_id={brick_en_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == brick_en_id
    assert data["target_lang"] == "en"
