from fastapi.testclient import TestClient

from database import Learner, LearnerSetting
from main import app
from services import auth_service


def test_get_pending_islands(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.get("/api/islands")

    app.dependency_overrides.clear()

    # Print things out to inspect them
    assert response.status_code == 200
    islands = response.json()
    assert len(islands) > 0
    for island in islands:
        assert island["id"] > 0
        assert island["brick_count"] >= 0


def test_create_island_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    col_name = "My New Test Island"
    response = client.post(
        "/api/islands",
        json={
            "name": col_name,
            "description": "A description for testing",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == col_name
    assert data["description"] == "A description for testing"
    assert data["creator_id"] == 2
    assert data["brick_count"] == 0
    assert data["learned_count"] == 0
    assert data["tags"] == []

    # Clean up test island
    from sqlmodel import select

    from database import Island, get_session

    session = next(get_session())
    created = session.exec(
        select(Island).where(Island.id == data["id"])
    ).first()
    if created:
        session.delete(created)
        session.commit()


def test_create_island_duplicate_name(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.post(
        "/api/islands",
        json={
            "name": "Island 1",
            "description": "Trying to duplicate Island 1",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "COLLECTION_ALREADY_EXISTS"


def test_create_island_empty_name(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.post(
        "/api/islands",
        json={
            "name": "   ",
            "description": "Empty name test",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_create_island_with_tags_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    col_name = "Island With Tags Test"
    response = client.post(
        "/api/islands",
        json={
            "name": col_name,
            "description": "A description for testing with tags",
            "tags": ["travel", "vocabulary"],
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == col_name
    assert data["description"] == "A description for testing with tags"
    assert data["creator_id"] == 2
    assert data["brick_count"] == 0
    assert data["learned_count"] == 0
    assert sorted(data["tags"]) == ["travel", "vocabulary"]

    # Verify Taggable in DB and cleanup
    from sqlmodel import select

    from database import Island, Taggable, get_session

    session = next(get_session())
    created = session.exec(
        select(Island).where(Island.id == data["id"])
    ).first()
    assert created is not None

    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == data["id"],
            Taggable.taggable_type == "Island",
        )
    ).all()
    assert len(taggables) == 2

    # Clean up
    client.delete(f"/api/islands/{data['id']}")
    session.delete(created)
    session.commit()


def test_update_island_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # First create a island
    create_res = client.post(
        "/api/islands",
        json={
            "name": "Update Island Test",
            "description": "Original description",
            "tags": ["initial_tag"],
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Now update it
    update_res = client.patch(
        f"/api/islands/{col_id}",
        json={
            "name": "Updated Island Name",
            "description": "Updated description",
            "tags": ["updated_tag1", "updated_tag2"],
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated Island Name"
    assert updated_data["description"] == "Updated description"
    assert sorted(updated_data["tags"]) == ["updatedtag1", "updatedtag2"]

    # Clean up via delete endpoint
    del_res = client.delete(f"/api/islands/{col_id}")
    assert del_res.status_code == 204

    app.dependency_overrides.clear()


def test_update_island_duplicate_name(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # Create island
    create_res = client.post(
        "/api/islands",
        json={
            "name": "Another Unique Island",
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Try to update to existing name "Island 1"
    update_res = client.patch(
        f"/api/islands/{col_id}",
        json={
            "name": "Island 1",
        },
    )
    assert update_res.status_code == 409
    assert update_res.json()["error_code"] == "COLLECTION_ALREADY_EXISTS"

    # Clean up
    client.delete(f"/api/islands/{col_id}")
    app.dependency_overrides.clear()


def test_delete_island_success(client: TestClient):
    existing_learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # Create island with tags
    create_res = client.post(
        "/api/islands",
        json={
            "name": "Delete Me Island",
            "tags": ["to_be_deleted"],
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Delete island
    del_res = client.delete(f"/api/islands/{col_id}")
    assert del_res.status_code == 204

    # Verify island and taggable are deleted
    from sqlmodel import select

    from database import Island, Taggable, get_session

    session = next(get_session())
    col = session.get(Island, col_id)
    assert col is None

    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == col_id,
            Taggable.taggable_type == "Island",
        )
    ).all()
    assert len(taggables) == 0

    app.dependency_overrides.clear()


def test_delete_island_forbidden(client: TestClient):
    other_learner = Learner(id=99999, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    # Try to delete island belonging to learner 2
    from sqlmodel import select

    from database import Island, get_session

    session = next(get_session())
    col = session.exec(
        select(Island).where(Island.name == "Odd Island")
    ).first()
    assert col is not None

    response = client.delete(f"/api/islands/{col.id}")
    assert response.status_code == 403

    app.dependency_overrides.clear()
