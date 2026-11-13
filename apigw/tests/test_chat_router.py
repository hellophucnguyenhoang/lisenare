import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from redis_client import get_redis_client
from schemas.chat import ChatMessage, ChatRole
from services import chat_service


@pytest.fixture
def client():
    with patch("database.init_db"), patch("database.delete_db_force"):
        with TestClient(app) as test_client:
            yield test_client


def test_get_chat_messages_empty(client: TestClient):
    session_id = "test-empty-session-12345"
    redis_client = get_redis_client()
    redis_client.delete(f"chat:{session_id}")

    response = client.get(f"/api/chat/{session_id}")
    assert response.status_code == 200
    assert response.json() == []


def test_get_chat_messages_existing_session(client: TestClient):
    session_id = "test-existing-session-12345"
    redis_client = get_redis_client()
    messages_payload = [
        {
            "role": "system",
            "content": "You are a friendly English teacher who keeps responses concise, clear, and to the point.",
        },
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
    ]
    redis_client.set(f"chat:{session_id}", json.dumps(messages_payload))

    response = client.get(f"/api/chat/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["role"] == "system"
    assert data[1]["role"] == "user"
    assert data[1]["content"] == "What is the capital of France?"
    assert data[2]["role"] == "assistant"
    assert data[2]["content"] == "The capital of France is Paris."

    redis_client.delete(f"chat:{session_id}")


def test_get_chat_messages_corrupt_data(client: TestClient):
    session_id = "test-corrupt-session-12345"
    redis_client = get_redis_client()
    redis_client.set(f"chat:{session_id}", "invalid-json")

    response = client.get(f"/api/chat/{session_id}")
    assert response.status_code == 200
    assert response.json() == []

    redis_client.delete(f"chat:{session_id}")


def test_get_chat_messages_service_unit():
    session_id = "test-service-unit-123"
    redis_client = get_redis_client()
    messages_payload = [
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hello! How can I help you?"},
    ]
    redis_client.set(f"chat:{session_id}", json.dumps(messages_payload))

    messages = chat_service.get_chat_messages(session_id)
    assert len(messages) == 2
    assert isinstance(messages[0], ChatMessage)
    assert messages[0].role == ChatRole.user
    assert messages[0].content == "Hello!"
    assert isinstance(messages[1], ChatMessage)
    assert messages[1].role == ChatRole.assistant
    assert messages[1].content == "Hello! How can I help you?"

    redis_client.delete(f"chat:{session_id}")
