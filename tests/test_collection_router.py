from fastapi.testclient import TestClient

from app.database import Learner
from app.main import app
from app.services import auth_service


def test_get_pending_collections(client: TestClient):
    existing_learner = Learner(id=2)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/collections/pending")

    app.dependency_overrides.clear()

    # Print things out to inspect them
    assert response.status_code == 200
    collections = response.json()
    for collection in collections:
        assert collection["id"] > 6  # <= 6 are system collections
        assert collection["brick_count"] > 0


def test_create_and_delete_collection_overrides(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # Create using system IDs
    create_response = client.post(
        "/collections/overrides", json={"collection_ids": [1, 3]}
    )
    assert create_response.status_code == 200
    create_data = create_response.json()

    # Extract the BRAND NEW cloned IDs from the nested response data
    cloned_user_ids = [
        item["cloned_collection_id"]
        for item in create_data["details"].values()
    ]

    # Delete using the correct user collection IDs
    delete_response = client.delete(
        "/collections/overrides", params={"collection_ids": cloned_user_ids}
    )
    assert delete_response.status_code == 200

    delete_data = delete_response.json()
    assert delete_data["total"] == create_data["total"]

    app.dependency_overrides.clear()
