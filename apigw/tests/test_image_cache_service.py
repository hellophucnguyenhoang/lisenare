from unittest.mock import MagicMock, patch

from sqlmodel import Session, select

from config import settings
from constants import (
    BRICK_IMAGE_CACHE_PREFIX,
    BRICK_IMAGES_DIR,
    IMAGE_CATCH_PREFIX,
)
from database import Brick, Island, Learner, engine
from main import app
from redis_client import get_redis_client
from schemas import BrickUpdate
from services import auth_service, brick_service
from services.image_cache_service import (
    cleanup_expired_image_files,
    clear_brick_image_cache,
)


def _setup_test_brick_with_image(learner_id: int = 2) -> Brick:
    with Session(engine) as session:
        learner = session.get(Learner, learner_id)
        if not learner:
            learner = Learner(id=learner_id, name=f"Test Learner {learner_id}")
            session.add(learner)
            session.commit()

        island = session.exec(
            select(Island).where(Island.creator_id == learner_id)
        ).first()
        if not island:
            island = Island(name="Test Island", creator_id=learner_id)
            session.add(island)
            session.commit()
            session.refresh(island)

        brick = session.exec(
            select(Brick).where(
                Brick.creator_id == learner_id,
                Brick.image_path.is_not(None),
            )
        ).first()
        if not brick:
            brick = Brick(
                native_text="Bức ảnh",
                target_text="A test photo",
                target_audio_path="learner-audios/learner-2/brick.wav",
                image_path=f"brick-images/learner-{learner_id}/brick-123.webp",
                kind="word",
                is_private=True,
                creator_id=learner_id,
                island_id=island.id,
            )
            session.add(brick)
            session.commit()
            session.refresh(brick)
        return brick


def test_brick_image_unauthenticated_fails(client):
    response = client.get("/api/bricks/1/image")
    assert response.status_code == 401


def test_brick_image_not_belonging_to_learner_fails(client):
    brick = _setup_test_brick_with_image(learner_id=2)
    with Session(engine) as session:
        db_b = session.get(Brick, brick.id)
        db_b.is_private = True
        session.add(db_b)
        session.commit()

    other_learner = Learner(id=999, name="Other Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    try:
        response = client.get(f"/api/bricks/{brick.id}/image")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_brick_image_no_image_fails(client):
    with Session(engine) as session:
        island = session.exec(
            select(Island).where(Island.creator_id == 2)
        ).first()
        no_img_brick = Brick(
            native_text="Không ảnh",
            target_text="No image here",
            target_audio_path="learner-audios/learner-2/brick.wav",
            image_path=None,
            kind="word",
            is_private=False,
            creator_id=2,
            island_id=island.id,
        )
        session.add(no_img_brick)
        session.commit()
        session.refresh(no_img_brick)
        brick_id = no_img_brick.id

    learner = Learner(id=2, name="Test Learner 2")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        response = client.get(f"/api/bricks/{brick_id}/image")
        assert response.status_code == 404
        assert "has no image" in response.json()["debug_message"]
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            b = session.get(Brick, brick_id)
            if b:
                session.delete(b)
                session.commit()


def test_public_brick_image_accessible_by_other_learner(client, tmp_path):
    brick = _setup_test_brick_with_image(learner_id=2)
    with Session(engine) as session:
        db_b = session.get(Brick, brick.id)
        db_b.is_private = False
        session.add(db_b)
        session.commit()

    other_learner = Learner(id=999, name="Other Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"PUBLIC_IMAGE_DATA")

    mock_download.side_effect = fake_download

    try:
        with (
            patch("services.image_cache_service.download_file", mock_download),
            patch("services.image_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/image")
            assert response.status_code == 200
            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.image_path.lstrip('/')}"
            assert response.json() == expected_url
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            db_b = session.get(Brick, brick.id)
            if db_b:
                db_b.is_private = True
                session.add(db_b)
                session.commit()


def test_brick_image_cache_miss_downloads_and_caches(client, tmp_path):
    brick = _setup_test_brick_with_image(learner_id=2)
    learner = Learner(id=2, name="Test Learner 2")

    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.delete(cache_key)

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"DOWNLOADED_IMAGE_DATA")

    mock_download.side_effect = fake_download

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.image_cache_service.download_file", mock_download),
            patch("services.image_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/image")
            assert response.status_code == 200
            full_url = response.json()

            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.image_path.lstrip('/')}"
            assert full_url == expected_url

            saved_file = tmp_path / brick.image_path
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"DOWNLOADED_IMAGE_DATA"
            assert mock_download.call_count == 1

            assert redis.exists(cache_key)
            ttl = redis.ttl(cache_key)
            assert 86300 <= ttl <= 86400
            assert redis.get(cache_key) == brick.image_path
            assert redis.exists(f"{IMAGE_CATCH_PREFIX}{brick.image_path}")
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_brick_image_cache_hit_returns_immediately(client, tmp_path):
    brick = _setup_test_brick_with_image(learner_id=2)
    learner = Learner(id=2, name="Test Learner 2")

    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.setex(cache_key, 86400, brick.image_path)
    redis.setex(f"{IMAGE_CATCH_PREFIX}{brick.image_path}", 86400, "1")

    local_file = tmp_path / brick.image_path
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"EXISTING_LOCAL_IMAGE")

    mock_download = MagicMock()

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.image_cache_service.download_file", mock_download),
            patch("services.image_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/image")
            assert response.status_code == 200
            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.image_path.lstrip('/')}"
            assert response.json() == expected_url
            mock_download.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_brick_image_cache_hit_repairs_missing_local_file(client, tmp_path):
    brick = _setup_test_brick_with_image(learner_id=2)
    learner = Learner(id=2, name="Test Learner 2")

    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.setex(cache_key, 86400, brick.image_path)

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"REPAIRED_IMAGE")

    mock_download.side_effect = fake_download

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.image_cache_service.download_file", mock_download),
            patch("services.image_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/image")
            assert response.status_code == 200

            saved_file = tmp_path / brick.image_path
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"REPAIRED_IMAGE"
            assert mock_download.call_count == 1
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_brick_update_clears_image_cache():
    brick = _setup_test_brick_with_image(learner_id=2)
    redis = get_redis_client()
    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick.id}"
    redis.set(cache_key, "some-old-image.webp")

    with Session(engine) as session:
        brick_service.update_brick(
            session=session,
            brick_id=brick.id,
            brick_update=BrickUpdate(
                image_path="brick-images/learner-2/new.webp"
            ),
            creator_id=2,
        )

    assert redis.get(cache_key) is None


def test_brick_delete_clears_image_cache():
    with Session(engine) as session:
        island = session.exec(
            select(Island).where(Island.creator_id == 2)
        ).first()
        brick = Brick(
            native_text="Xoá ảnh",
            target_text="Delete image test",
            target_audio_path="learner-audios/learner-2/brick.wav",
            image_path="brick-images/learner-2/delete-me.webp",
            kind="word",
            is_private=True,
            creator_id=2,
            island_id=island.id,
        )
        session.add(brick)
        session.commit()
        session.refresh(brick)
        brick_id = brick.id

    redis = get_redis_client()
    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}{brick_id}"
    redis.set(cache_key, "brick-images/learner-2/delete-me.webp")

    with Session(engine) as session:
        brick_service.delete_brick(session, 2, brick_id)

    assert redis.get(cache_key) is None


def test_clear_brick_image_cache_direct():
    redis = get_redis_client()
    cache_key = f"{BRICK_IMAGE_CACHE_PREFIX}8888"
    redis.set(cache_key, "some-image.webp")
    clear_brick_image_cache(8888)
    assert redis.get(cache_key) is None


def test_cleanup_expired_image_files(tmp_path):
    assets_dir = tmp_path
    brick_images_dir = assets_dir / BRICK_IMAGES_DIR / "learner-2"
    brick_images_dir.mkdir(parents=True, exist_ok=True)

    active_file = brick_images_dir / "active.webp"
    active_file.write_bytes(b"ACTIVE_IMAGE")

    expired_file = brick_images_dir / "expired.webp"
    expired_file.write_bytes(b"EXPIRED_IMAGE")

    # Non-brick image (e.g. learner avatar) must NOT be deleted
    avatar_dir = assets_dir / "learner-avatars/learner-2"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    avatar_file = avatar_dir / "avatar.webp"
    avatar_file.write_bytes(b"AVATAR_IMAGE")

    redis = get_redis_client()
    active_rel_path = active_file.relative_to(assets_dir).as_posix()
    redis.setex(f"{IMAGE_CATCH_PREFIX}{active_rel_path}", 60, "1")

    with patch("services.image_cache_service.ASSETS_DIR", assets_dir):
        deleted = cleanup_expired_image_files(directory=assets_dir)

    assert str(expired_file) in deleted
    assert not expired_file.exists()
    assert active_file.exists()
    assert avatar_file.exists()  # Avatar must be preserved!
