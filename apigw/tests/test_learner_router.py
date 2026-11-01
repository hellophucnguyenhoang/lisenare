import io
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from config import settings
from database import Learner, LearnerSetting, engine
from main import app
from services import auth_service


def _get_or_create_learner_2(session: Session) -> Learner:
    learner = session.get(Learner, 2)
    if not learner:
        learner = Learner(
            id=2, name="Test Learner 2", avatar_path="default-images/meo.webp"
        )
        session.add(learner)
        session.commit()
    setting = session.get(LearnerSetting, 2)
    if not setting:
        setting = LearnerSetting(learner_id=2, retrieval_lang="en")
        session.add(setting)
        session.commit()
    return Learner(
        id=2,
        name=learner.name or "Test Learner 2",
        avatar_path=learner.avatar_path or "default-images/meo.webp",
    )


def test_get_learner_me(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)
        db_l = session.get(Learner, 2)
        db_l.avatar_path = "default-images/meo.webp"
        session.add(db_l)
        session.commit()
        session.refresh(db_l)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.get("/api/learners/me")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert "name" in data
    assert data["retrieval_lang"] == "en"
    assert data["avatar_path"] == "default-images/meo.webp"


def test_update_learner_retrieval_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch("/api/learners/me", json={"retrieval_lang": "ja"})
    assert response.status_code == 200
    data = response.json()
    assert data["retrieval_lang"] == "ja"

    # Verify directly in DB
    with Session(engine) as session:
        setting = session.get(LearnerSetting, 2)
        assert setting is not None
        assert setting.retrieval_lang == "ja"

        # Restore to en
        setting.retrieval_lang = "en"
        session.add(setting)
        session.commit()

    app.dependency_overrides.clear()


def test_update_learner_name(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None
        orig_name = learner_in_db.name

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch("/api/learners/me", json={"name": "Updated Name"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"

    # Restore original name
    with Session(engine) as session:
        learner = session.get(Learner, 2)
        learner.name = orig_name
        session.add(learner)
        session.commit()

    app.dependency_overrides.clear()


def test_update_learner_both_name_and_retrieval_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None
        orig_name = learner_in_db.name

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch(
        "/api/learners/me",
        json={"name": "Bilingual Learner", "retrieval_lang": "fr"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bilingual Learner"
    assert data["retrieval_lang"] == "fr"

    # Verify and restore
    with Session(engine) as session:
        learner = session.get(Learner, 2)
        learner.name = orig_name
        setting = session.get(LearnerSetting, 2)
        if setting:
            setting.retrieval_lang = "en"
            session.add(setting)
        session.add(learner)
        session.commit()

    app.dependency_overrides.clear()


def test_update_learner_invalid_retrieval_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    # Too long
    response = client.patch("/api/learners/me", json={"retrieval_lang": "eng"})
    assert response.status_code == 422

    # Too short
    response = client.patch("/api/learners/me", json={"retrieval_lang": "e"})
    assert response.status_code == 422

    app.dependency_overrides.clear()


def _create_sample_image_bytes() -> bytes:
    img = Image.new("RGBA", (100, 100), color=(0, 200, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_avatar_patch_success(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    img_bytes = _create_sample_image_bytes()

    with patch("cloud_storage_client.upload_bytes") as mock_upload:
        response = client.patch(
            "/api/learners/me/avatar",
            files={"avatar_file": ("profile.png", img_bytes, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert data["avatar_path"] is not None
        assert data["avatar_path"].startswith(
            "learner-avatars/learner-2/avatar-"
        )
        assert data["avatar_path"].endswith(".webp")

        mock_upload.assert_called_once()
        _, kwargs = mock_upload.call_args
        assert kwargs["content_type"] == "image/webp"

    # Verify GET /me also returns the avatar_path
    me_response = client.get("/api/learners/me")
    assert me_response.status_code == 200
    assert me_response.json()["avatar_path"] == data["avatar_path"]

    # Verify DB
    with Session(engine) as session:
        learner = session.get(Learner, 2)
        assert learner.avatar_path == data["avatar_path"]

    app.dependency_overrides.clear()


def test_upload_avatar_invalid_image(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch(
        "/api/learners/me/avatar",
        files={
            "avatar_file": (
                "broken.txt",
                b"corrupted file content",
                "text/plain",
            )
        },
    )
    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_upload_avatar_empty_file(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch(
        "/api/learners/me/avatar",
        files={"avatar_file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_upload_avatar_no_file(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch("/api/learners/me/avatar")
    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_update_avatar_path_via_patch_me(client: TestClient):
    with Session(engine) as session:
        learner = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    response = client.patch(
        "/api/learners/me",
        json={"avatar_path": "learner-avatars/learner-2/custom_avatar.webp"},
    )
    assert response.status_code == 200
    assert (
        response.json()["avatar_path"]
        == "learner-avatars/learner-2/custom_avatar.webp"
    )

    # Reset
    with Session(engine) as session:
        db_l = session.get(Learner, 2)
        db_l.avatar_path = "default-images/meo.webp"
        session.add(db_l)
        session.commit()

    app.dependency_overrides.clear()


def test_get_learner_avatar_unauthenticated(client: TestClient):
    response = client.post("/api/learners/avatar", json={"learner_id": 2})
    assert response.status_code == 401


def test_get_learner_avatar_not_found(client: TestClient):
    with Session(engine) as session:
        learner_in_db = _get_or_create_learner_2(session)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.post("/api/learners/avatar", json={"learner_id": 999999})
    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_get_learner_avatar_downloads_if_missing(client: TestClient, tmp_path):
    with Session(engine) as session:
        learner = _get_or_create_learner_2(session)
        learner_db = session.get(Learner, 2)
        learner_db.avatar_path = "learner-avatars/learner-2/avatar-test.webp"
        session.add(learner_db)
        session.commit()

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"WEBP_AVATAR_DATA")

    mock_download.side_effect = fake_download

    try:
        with (
            patch("services.learner_service.download_file", mock_download),
            patch("services.learner_service.ASSETS_DIR", tmp_path),
        ):
            response = client.post(
                "/api/learners/avatar", json={"learner_id": 2}
            )
            assert response.status_code == 200
            full_url = response.json()

            expected_url = f"{settings.asset_base_url.rstrip('/')}/learner-avatars/learner-2/avatar-test.webp"
            assert full_url == expected_url

            saved_file = (
                tmp_path / "learner-avatars/learner-2/avatar-test.webp"
            )
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"WEBP_AVATAR_DATA"
            assert mock_download.call_count == 1
    finally:
        with Session(engine) as session:
            learner_db = session.get(Learner, 2)
            learner_db.avatar_path = "default-images/meo.webp"
            session.add(learner_db)
            session.commit()
        app.dependency_overrides.clear()


def test_get_learner_avatar_already_on_disk_returns_immediately(
    client: TestClient, tmp_path
):
    with Session(engine) as session:
        learner = _get_or_create_learner_2(session)
        learner_db = session.get(Learner, 2)
        learner_db.avatar_path = "learner-avatars/learner-2/avatar-cached.webp"
        session.add(learner_db)
        session.commit()

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    avatar_path = "learner-avatars/learner-2/avatar-cached.webp"
    local_file = tmp_path / avatar_path
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"EXISTING_AVATAR")

    mock_download = MagicMock()

    try:
        with (
            patch("services.learner_service.download_file", mock_download),
            patch("services.learner_service.ASSETS_DIR", tmp_path),
        ):
            response = client.post(
                "/api/learners/avatar", json={"learner_id": 2}
            )
            assert response.status_code == 200
            expected_url = (
                f"{settings.asset_base_url.rstrip('/')}/{avatar_path}"
            )
            assert response.json() == expected_url

            mock_download.assert_not_called()
    finally:
        with Session(engine) as session:
            learner_db = session.get(Learner, 2)
            learner_db.avatar_path = "default-images/meo.webp"
            session.add(learner_db)
            session.commit()
        app.dependency_overrides.clear()
