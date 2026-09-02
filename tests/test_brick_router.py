import io
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import select

from app.database import Brick, Collection, Learner, Taggable, get_session
from app.main import app
from app.services import auth_service


def test_create_brick_with_tags_success(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    session = next(get_session())
    col = session.exec(
        select(Collection).where(Collection.creator_id == 2)
    ).first()
    assert col is not None

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Hello world unique test brick",
        "collection_id": col.id,
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
    assert data["collection_id"] == col.id
    assert sorted(data["tags"]) == ["basic", "greeting"]
    brick_id = data["id"]

    # Verify Taggable records exist in DB
    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == brick_id,
            Taggable.taggable_type == "Brick",
        )
    ).all()
    assert len(taggables) == 2

    # Update tags
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )
    update_payload = {"tags": ["advanced", "phrases"]}
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

    # Delete brick and verify taggables are removed
    with patch(
        "app.services.context_search_service.delete_item_from_vector_store"
    ):
        del_response = client.delete(f"/bricks/{brick_id}")
    assert del_response.status_code == 204

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


def test_create_brick_collection_not_found(client: TestClient):
    existing_learner = Learner(id=2)
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
    other_learner = Learner(id=99999)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    session = next(get_session())
    col = session.exec(
        select(Collection).where(Collection.creator_id == 2)
    ).first()
    assert col is not None

    brick_payload = {
        "native_text": "Xin chào",
        "target_text": "Test forbidden",
        "collection_id": col.id,
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
