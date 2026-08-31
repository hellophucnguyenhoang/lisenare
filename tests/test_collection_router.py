from fastapi.testclient import TestClient

from app.database import Learner
from app.main import app
from app.services import auth_service


def test_get_pending_collections(client: TestClient):
    existing_learner = Learner(id=2)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/collections")

    app.dependency_overrides.clear()

    # Print things out to inspect them
    assert response.status_code == 200
    collections = response.json()
    for collection in collections:
        assert collection["id"] > 0
        assert collection["brick_count"] > 0
