import uuid
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
        owner = _ensure_learner(session, 9, "PrivateOwnerSeed")
        owner_col = _ensure_collection(session, owner.id, "Private Owner Col")
        brick = Brick(
            native_text="VN: Private",
            target_text="Private text from owner seed",
            target_audio_path="system-brick-audios/seed.wav",
            unit_type="sentence",
            is_private=True,
            creator_id=owner.id,
            collection_id=owner_col.id,
        )
        session.add(brick)
        session.commit()
        session.refresh(brick)
        brick_id = brick.id

        other_learner = _ensure_learner(session, 3, "Other")
        other_col = _ensure_collection(session, other_learner.id, "Other Col")
        other_col_id = other_col.id

    other_learner = Learner(id=3, name="Other", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )
    try:
        response = client.post(
            f"/api/bricks/add-from/{brick_id}",
            json={"collection_id": other_col_id},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_add_public_brick_success(client: TestClient):
    """Add a public brick from another learner successfully."""
    uid = uuid.uuid4().hex[:6]
    target_text = f"unique test sentence for add {uid}"
    with Session(engine) as session:
        owner = _ensure_learner(session, 10, "Owner")
        owner_col = _ensure_collection(session, owner.id, "Owner Collection")
        public_brick = _create_public_brick(
            session,
            owner.id,
            owner_col.id,
            target_text,
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
        assert data["target_text"] == target_text
        assert data["creator_id"] == 11
        assert data["collection_id"] == adder_col_id
        assert data["is_private"] is True  # copied bricks default to private
    finally:
        app.dependency_overrides.clear()


def test_add_brick_duplicate_conflict(client: TestClient):
    """Adding a brick that already exists in the learner's library returns 409."""
    uid = uuid.uuid4().hex[:6]
    dup_text = f"duplicate brick text for test {uid}"
    with Session(engine) as session:
        owner = _ensure_learner(session, 10, "Owner")
        owner_col = _ensure_collection(session, owner.id, "Owner Collection")
        public_brick = _create_public_brick(
            session,
            owner.id,
            owner_col.id,
            dup_text,
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
            dup_text,
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
    uid = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        owner = _ensure_learner(session, 20, "CollOwner")
        owner_col = _ensure_collection(
            session, owner.id, f"Shared Collection {uid}"
        )

        _create_public_brick(
            session, owner.id, owner_col.id, f"collection brick alpha {uid}"
        )
        _create_public_brick(
            session, owner.id, owner_col.id, f"collection brick beta {uid}"
        )
        # This one is private — should NOT be copied
        private_brick = Brick(
            native_text="VN: private",
            target_text=f"collection brick gamma private {uid}",
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
        adder_col = _ensure_collection(
            session, adder.id, f"My Target Col {uid}"
        )
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
    uid = uuid.uuid4().hex[:6]
    with Session(engine) as session:
        owner = _ensure_learner(session, 22, "SkipOwner")
        owner_col = _ensure_collection(session, owner.id, f"Skip Source {uid}")
        _create_public_brick(
            session, owner.id, owner_col.id, f"skip test brick one {uid}"
        )
        _create_public_brick(
            session, owner.id, owner_col.id, f"skip test brick two {uid}"
        )
        owner_col_id = owner_col.id

        adder = _ensure_learner(session, 23, "SkipAdder")
        adder_col = _ensure_collection(session, adder.id, f"Skip Target {uid}")
        adder_col_id = adder_col.id

        # Pre-create one of the bricks for the adder
        _create_public_brick(
            session, adder.id, adder_col.id, f"skip test brick one {uid}"
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


# --- Get brick detail tests ---


def test_get_brick_detail_unauthenticated(client: TestClient):
    """Accessing brick detail without authentication should fail (401)."""
    response = client.get("/api/bricks/1")
    assert response.status_code == 401


def test_get_brick_detail_not_found(client: TestClient):
    """Accessing non-existent brick should return 404."""
    learner = Learner(id=2, name="Test", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )
    try:
        response = client.get("/api/bricks/999999")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_brick_detail_private_from_another_learner_forbidden(
    client: TestClient,
):
    """Cannot fetch detail of another learner's private brick (403)."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 30, "PrivateOwner")
        owner_col = _ensure_collection(session, owner.id, "Private Col")
        private_brick = Brick(
            native_text="VN: Secret",
            target_text="Secret private sentence",
            target_audio_path="system-brick-audios/secret.wav",
            unit_type="sentence",
            is_private=True,
            creator_id=owner.id,
            collection_id=owner_col.id,
        )
        session.add(private_brick)
        session.commit()
        session.refresh(private_brick)
        brick_id = private_brick.id

    other_learner = Learner(id=31, name="Snooper", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )
    try:
        response = client.get(f"/api/bricks/{brick_id}")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_get_brick_detail_own_private_brick_success(client: TestClient):
    """Learner can fetch detail of their own private brick with collection name and can_add=False."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 32, "MyOwner")
        owner_col = _ensure_collection(session, owner.id, "My Special Col")
        private_brick = Brick(
            native_text="VN: My secret",
            target_text="My private sentence detail",
            target_audio_path="system-brick-audios/my_secret.wav",
            unit_type="sentence",
            is_private=True,
            creator_id=owner.id,
            collection_id=owner_col.id,
        )
        session.add(private_brick)
        session.commit()
        session.refresh(private_brick)
        brick_id = private_brick.id

    owner_learner = Learner(id=32, name="MyOwner", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        owner_learner
    )
    try:
        response = client.get(f"/api/bricks/{brick_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == brick_id
        assert data["target_text"] == "My private sentence detail"
        assert data["creator_id"] == 32
        assert data["creator"]["name"] == "MyOwner"
        assert data["collection_name"] == "My Special Col"
    finally:
        app.dependency_overrides.clear()


def test_get_brick_detail_public_from_another_learner_success(
    client: TestClient,
):
    """Learner can fetch detail of a public brick with collection name."""
    with Session(engine) as session:
        owner = _ensure_learner(session, 33, "PublicCreator")
        owner_col = _ensure_collection(session, owner.id, "Public Col Name")
        public_brick = _create_public_brick(
            session, owner.id, owner_col.id, "Public detail sentence test"
        )
        brick_id = public_brick.id

    viewer = Learner(id=34, name="Viewer", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        viewer
    )
    try:
        response = client.get(f"/api/bricks/{brick_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == brick_id
        assert data["target_text"] == "Public detail sentence test"
        assert data["creator_id"] == 33
        assert data["creator"]["name"] == "PublicCreator"
        assert data["collection_name"] == "Public Col Name"
        assert data["is_private"] is False
    finally:
        app.dependency_overrides.clear()


def test_search_bricks_lightweight_without_creator_name(client: TestClient):
    """Search results should not have creator_name and remain lightweight."""
    from schemas import BrickContextSearch
    from services.context_search_service import context_search_service

    # Verify model fields: creator_name must not be in BrickContextSearch
    assert "creator_name" not in BrickContextSearch.model_fields

    with Session(engine) as session:
        owner = _ensure_learner(session, 35, "SearchOwner")
        owner_col = _ensure_collection(session, owner.id, "Search Col")
        _create_public_brick(
            session, owner.id, owner_col.id, "Zebra unique search target"
        )

        with patch.object(
            context_search_service,
            "search_bricks_semantic",
            return_value=[],
        ):
            results = context_search_service.search_bricks(
                session=session,
                query="Zebra",
                searcher_id=35,
            )
        assert len(results) > 0
        match = next(
            (
                r
                for r in results
                if r.target_text == "Zebra unique search target"
            ),
            None,
        )
        assert match is not None
        assert match.is_own is True
        assert (
            not hasattr(match, "creator_name")
            or getattr(match, "creator_name", None) is None
        )


def test_search_bricks_endpoint_unauthenticated_fails(client: TestClient):
    """Calling search endpoint without auth returns 401."""
    response = client.post(
        "/api/context-search/bricks-search",
        json={"query": "test query"},
    )
    assert response.status_code == 401


def test_search_bricks_endpoint_authenticated_success(client: TestClient):
    """Calling search endpoint with authenticated learner returns 200."""
    from services.context_search_service import context_search_service

    learner = Learner(id=2, name="Searcher", setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )
    try:
        with patch.object(
            context_search_service,
            "search_bricks_semantic",
            return_value=[],
        ):
            response = client.post(
                "/api/context-search/bricks-search",
                json={"query": "hello"},
            )
            assert response.status_code == 200
            assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_search_bricks_unit_type_filter_and_pagination():
    """unit_type filters results; limit/offset paginate them."""
    from services.context_search_service import context_search_service

    token = f"tok{uuid.uuid4().hex[:10]}"
    with Session(engine) as session:
        owner = _ensure_learner(session, 36, "FilterOwner")
        col = _ensure_collection(session, owner.id, "Filter Col")
        word = _create_public_brick(session, owner.id, col.id, token)
        word.unit_type = "word"
        session.add(word)
        session.commit()
        for i in range(3):
            _create_public_brick(
                session, owner.id, col.id, f"{token} sentence {i}"
            )

        with patch.object(
            context_search_service, "search_bricks_semantic", return_value=[]
        ):
            search = context_search_service.search_bricks
            words = search(session, token, 36, unit_type="word")
            sentences = search(session, token, 36, unit_type="sentence")
            page1 = search(session, token, 36, limit=2)
            page2 = search(session, token, 36, limit=2, offset=2)

        assert [r.brick_id for r in words] == [word.id]
        assert len(sentences) == 3
        assert word.id not in {r.brick_id for r in sentences}
        assert len(page1) == 2 and len(page2) == 2
        assert not {r.brick_id for r in page1} & {r.brick_id for r in page2}
