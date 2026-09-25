from unittest.mock import patch

from fastapi.testclient import TestClient

from database import Learner
from main import app
from schemas import InteractionType
from services import auth_service


def test_create_brick_interaction_unauthenticated_listen():
    client = TestClient(app)
    app.dependency_overrides[
        auth_service.decode_token_get_optional_learner
    ] = lambda: None

    with patch(
        "app.services.brick_interaction_service.handle_interaction_and_update_profile"
    ) as mock_handle:
        response = client.post(
            "/brick-interactions",
            json={
                "session_id": "test_sess_123",
                "brick_id": 1,
                "interaction_type": InteractionType.LISTEN.value,
            },
        )
        assert response.status_code == 201
        assert mock_handle.called

    app.dependency_overrides.clear()


def test_create_brick_interaction_authenticated_like():
    client = TestClient(app)
    fake_learner = Learner(id=2, name="test_learner")
    app.dependency_overrides[
        auth_service.decode_token_get_optional_learner
    ] = lambda: fake_learner

    with patch(
        "app.services.brick_interaction_service.handle_interaction_and_update_profile"
    ) as mock_handle:
        response = client.post(
            "/brick-interactions",
            json={
                "session_id": "test_sess_123",
                "brick_id": 1,
                "interaction_type": InteractionType.LIKE.value,
            },
        )
        assert response.status_code == 201
        assert mock_handle.called
        assert mock_handle.call_args[1]["learner_id"] == 2

    app.dependency_overrides.clear()
