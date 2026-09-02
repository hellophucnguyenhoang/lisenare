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
    assert len(collections) > 0
    for collection in collections:
        assert collection["id"] > 0
        assert collection["brick_count"] >= 0


def test_create_collection_success(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    col_name = "My New Test Collection"
    response = client.post(
        "/collections",
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

    # Clean up test collection
    from app.database import Collection, get_session
    from sqlmodel import select

    session = next(get_session())
    created = session.exec(
        select(Collection).where(Collection.id == data["id"])
    ).first()
    if created:
        session.delete(created)
        session.commit()


def test_create_collection_duplicate_name(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.post(
        "/collections",
        json={
            "name": "Odd Collection",
            "description": "Trying to duplicate Odd Collection",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "COLLECTION_ALREADY_EXISTS"


def test_create_collection_empty_name(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    response = client.post(
        "/collections",
        json={
            "name": "   ",
            "description": "Empty name test",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_create_collection_with_tags_success(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    col_name = "Collection With Tags Test"
    response = client.post(
        "/collections",
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
    from app.database import Collection, Taggable, get_session
    from sqlmodel import select

    session = next(get_session())
    created = session.exec(
        select(Collection).where(Collection.id == data["id"])
    ).first()
    assert created is not None

    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == data["id"],
            Taggable.taggable_type == "Collection",
        )
    ).all()
    assert len(taggables) == 2

    # Clean up
    client.delete(f"/collections/{data['id']}")
    session.delete(created)
    session.commit()


def test_update_collection_success(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # First create a collection
    create_res = client.post(
        "/collections",
        json={
            "name": "Update Collection Test",
            "description": "Original description",
            "tags": ["initial_tag"],
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Now update it
    update_res = client.patch(
        f"/collections/{col_id}",
        json={
            "name": "Updated Collection Name",
            "description": "Updated description",
            "tags": ["updated_tag1", "updated_tag2"],
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated Collection Name"
    assert updated_data["description"] == "Updated description"
    assert sorted(updated_data["tags"]) == ["updated_tag1", "updated_tag2"]

    # Clean up via delete endpoint
    del_res = client.delete(f"/collections/{col_id}")
    assert del_res.status_code == 204

    app.dependency_overrides.clear()


def test_update_collection_duplicate_name(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # Create collection
    create_res = client.post(
        "/collections",
        json={
            "name": "Another Unique Collection",
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Try to update to existing name "Odd Collection"
    update_res = client.patch(
        f"/collections/{col_id}",
        json={
            "name": "Odd Collection",
        },
    )
    assert update_res.status_code == 409
    assert update_res.json()["error_code"] == "COLLECTION_ALREADY_EXISTS"

    # Clean up
    client.delete(f"/collections/{col_id}")
    app.dependency_overrides.clear()


def test_delete_collection_success(client: TestClient):
    existing_learner = Learner(id=2)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        existing_learner
    )

    # Create collection with tags
    create_res = client.post(
        "/collections",
        json={
            "name": "Delete Me Collection",
            "tags": ["to_be_deleted"],
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Delete collection
    del_res = client.delete(f"/collections/{col_id}")
    assert del_res.status_code == 204

    # Verify collection and taggable are deleted
    from app.database import Collection, Taggable, get_session
    from sqlmodel import select

    session = next(get_session())
    col = session.get(Collection, col_id)
    assert col is None

    taggables = session.exec(
        select(Taggable).where(
            Taggable.taggable_id == col_id,
            Taggable.taggable_type == "Collection",
        )
    ).all()
    assert len(taggables) == 0

    app.dependency_overrides.clear()


def test_delete_collection_forbidden(client: TestClient):
    other_learner = Learner(id=99999)
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    # Try to delete collection belonging to learner 2
    from app.database import Collection, get_session
    from sqlmodel import select

    session = next(get_session())
    col = session.exec(
        select(Collection).where(Collection.name == "Odd Collection")
    ).first()
    assert col is not None

    response = client.delete(f"/collections/{col.id}")
    assert response.status_code == 403

    app.dependency_overrides.clear()
