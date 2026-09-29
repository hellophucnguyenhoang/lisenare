from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import Brick, Collection, Learner, LearnerSetting, engine
from main import app
from services import auth_service


def _ensure_learner(session: Session, learner_id: int, name: str) -> Learner:
    learner = session.get(Learner, learner_id)
    if not learner:
        learner = Learner(id=learner_id, name=name, setting=LearnerSetting())
        session.add(learner)
        session.commit()
        session.refresh(learner)
    return learner


def _ensure_collection(
    session: Session, creator_id: int, name: str
) -> Collection:
    col = session.exec(
        select(Collection).where(
            Collection.creator_id == creator_id, Collection.name == name
        )
    ).first()
    if not col:
        col = Collection(name=name, creator_id=creator_id)
        session.add(col)
        session.commit()
        session.refresh(col)
    return col


def _create_public_brick(
    session: Session,
    creator_id: int,
    collection_id: int,
    target_text: str,
) -> Brick:
    brick = Brick(
        native_text=f"VN: {target_text}",
        target_text=target_text,
        target_audio_path=f"system-brick-audios/{target_text.replace(' ', '_')}.wav",
        unit_type="sentence",
        is_private=False,
        creator_id=creator_id,
        collection_id=collection_id,
    )
    session.add(brick)
    session.commit()
    session.refresh(brick)
    return brick


# --- Add single brick tests ---


def test_add_brick_unauthenticated(client: TestClient):
    response = client.post("/api/bricks/add-from/1", json={"collection_id": 1})
    assert response.status_code == 401


def test_add_brick_not_found(client: TestClient):
    learner = Learner(id=2, name="Test", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )
    try:
        response = client.post(
            "/api/bricks/add-from/999999", json={"collection_id": 1}
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_add_private_brick_from_another_learner_forbidden(client: TestClient):
    """Cannot add a private brick from another learner."""
    with Session(engine) as session:
        # Learner 2 has private bricks from seed data
        brick = session.exec(
            select(Brick).where(
                Brick.creator_id == 2,
                Brick.is_private == True,  # noqa: E712
            )
        ).first()
        assert brick is not None
        brick_id = brick.id

    # Learner 3 tries to add it
    other_learner = Learner(id=3, name="Other", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )
    try:
        response = client.post(
            f"/api/bricks/add-from/{brick_id}", json={"collection_id": 1}
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_add_public_brick_success(client: TestClient):
    """Add a public brick from another learner successfully."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 10, "Owner")
        owner_col = _ensure_collection(session, owner.id, "Owner Collection")
        public_brick = _create_public_brick(
            session,
            owner.id,
            owner_col.id,
            "unique test sentence for add",
        )
        public_brick_id = public_brick.id

        adder = _ensure_learner(session, 11, "Adder")
        adder_col = _ensure_collection(session, adder.id, "My Collection")
        adder_col_id = adder_col.id

    adder_learner = Learner(id=11, name="Adder", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        adder_learner
    )
    try:
        with patch("services.context_search_service.add_item_to_vector_store"):
            response = client.post(
                f"/api/bricks/add-from/{public_brick_id}",
                json={"collection_id": adder_col_id},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["target_text"] == "unique test sentence for add"
        assert data["creator_id"] == 11
        assert data["collection_id"] == adder_col_id
        assert data["is_private"] is True  # copied bricks default to private
    finally:
        app.dependency_overrides.clear()


def test_add_brick_duplicate_conflict(client: TestClient):
    """Adding a brick that already exists in the learner's library returns 409."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 10, "Owner")
        owner_col = _ensure_collection(session, owner.id, "Owner Collection")
        public_brick = _create_public_brick(
            session,
            owner.id,
            owner_col.id,
            "duplicate brick text for test",
        )
        public_brick_id = public_brick.id

        adder = _ensure_learner(session, 12, "Adder2")
        adder_col = _ensure_collection(session, adder.id, "Adder2 Collection")
        adder_col_id = adder_col.id

        # Pre-create the same brick for the adder
        _create_public_brick(
            session,
            adder.id,
            adder_col.id,
            "duplicate brick text for test",
        )

    adder_learner = Learner(id=12, name="Adder2", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        adder_learner
    )
    try:
        response = client.post(
            f"/api/bricks/add-from/{public_brick_id}",
            json={"collection_id": adder_col_id},
        )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


# --- Add collection tests ---


def test_add_collection_unauthenticated(client: TestClient):
    response = client.post(
        "/api/bricks/add-from-collection/1",
        json={"target_collection_id": 1},
    )
    assert response.status_code == 401


def test_add_collection_source_not_found(client: TestClient):
    learner = Learner(id=2, name="Test", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )
    try:
        response = client.post(
            "/api/bricks/add-from-collection/999999",
            json={"target_collection_id": 1},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_add_bricks_from_collection_success(client: TestClient):
    """Add all public bricks from another learner's collection."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 20, "CollOwner")
        owner_col = _ensure_collection(session, owner.id, "Shared Collection")

        _create_public_brick(
            session, owner.id, owner_col.id, "collection brick alpha"
        )
        _create_public_brick(
            session, owner.id, owner_col.id, "collection brick beta"
        )
        # This one is private — should NOT be copied
        private_brick = Brick(
            native_text="VN: private",
            target_text="collection brick gamma private",
            target_audio_path="system-brick-audios/gamma.wav",
            unit_type="sentence",
            is_private=True,
            creator_id=owner.id,
            collection_id=owner_col.id,
        )
        session.add(private_brick)
        session.commit()
        owner_col_id = owner_col.id

        adder = _ensure_learner(session, 21, "CollAdder")
        adder_col = _ensure_collection(session, adder.id, "My Target Col")
        adder_col_id = adder_col.id

    adder_learner = Learner(id=21, name="CollAdder", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        adder_learner
    )
    try:
        response = client.post(
            f"/api/bricks/add-from-collection/{owner_col_id}",
            json={"target_collection_id": adder_col_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 2  # only the 2 public bricks
        assert data["skipped"] == 0
    finally:
        app.dependency_overrides.clear()


def test_add_bricks_from_collection_skips_duplicates(client: TestClient):
    """Duplicates are skipped, not causing errors."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 22, "SkipOwner")
        owner_col = _ensure_collection(session, owner.id, "Skip Source")
        _create_public_brick(
            session, owner.id, owner_col.id, "skip test brick one"
        )
        _create_public_brick(
            session, owner.id, owner_col.id, "skip test brick two"
        )
        owner_col_id = owner_col.id

        adder = _ensure_learner(session, 23, "SkipAdder")
        adder_col = _ensure_collection(session, adder.id, "Skip Target")
        adder_col_id = adder_col.id

        # Pre-create one of the bricks for the adder
        _create_public_brick(
            session, adder.id, adder_col.id, "skip test brick one"
        )

    adder_learner = Learner(id=23, name="SkipAdder", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        adder_learner
    )
    try:
        response = client.post(
            f"/api/bricks/add-from-collection/{owner_col_id}",
            json={"target_collection_id": adder_col_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 1
        assert data["skipped"] == 1
    finally:
        app.dependency_overrides.clear()
