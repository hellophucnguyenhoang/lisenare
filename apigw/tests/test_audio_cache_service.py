from unittest.mock import MagicMock, patch

from sqlmodel import Session, select

from config import settings
from constants import (
    AUDIO_CATCH_PREFIX,
    BRICK_CACHE_PREFIX,
)
from database import Brick, Collection, Learner, engine
from main import app
from redis_client import get_redis_client
from services import auth_service
from services.audio_cache_service import (
    cleanup_expired_audio_files,
)


def _setup_test_brick(learner_id: int = 1) -> Brick:
    """Helper to ensure a brick exists for the given learner."""
    with Session(engine) as session:
        learner = session.get(Learner, learner_id)
        if not learner:
            learner = Learner(id=learner_id, name="Test Learner")
            session.add(learner)
            session.commit()

        collection = session.exec(
            select(Collection).where(Collection.creator_id == learner_id)
        ).first()
        if not collection:
            collection = Collection(name="Test Col", creator_id=learner_id)
            session.add(collection)
            session.commit()
            session.refresh(collection)

        brick = session.exec(
            select(Brick).where(Brick.creator_id == learner_id)
        ).first()
        if not brick:
            brick = Brick(
                native_text="Xin chao",
                target_text="Hello",
                target_audio_path="system-brick-audios/hello.wav",
                unit_type="word",
                creator_id=learner_id,
                collection_id=collection.id,
            )
            session.add(brick)
            session.commit()
            session.refresh(brick)
        return brick


def test_brick_audio_unauthenticated_fails(client):
    """Accessing the brick audio endpoint without authentication should fail (401)."""
    response = client.get("/api/bricks/1/audio")
    assert response.status_code == 401


def test_brick_audio_not_belonging_to_learner_fails(client):
    """Accessing a private brick that does not belong to the learner should return 404."""
    brick = _setup_test_brick(learner_id=1)

    other_learner = Learner(id=999, name="Other Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    try:
        response = client.get(f"/api/bricks/{brick.id}/audio")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_public_brick_audio_accessible_by_other_learner(client, tmp_path):
    """Accessing a public brick belonging to another learner should succeed (200)."""
    brick = _setup_test_brick(learner_id=1)
    with Session(engine) as session:
        db_brick = session.get(Brick, brick.id)
        db_brick.is_private = False
        session.add(db_brick)
        session.commit()

    other_learner = Learner(id=999, name="Other Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"PUBLIC_AUDIO_DATA")

    mock_download.side_effect = fake_download

    try:
        with (
            patch("services.audio_cache_service.download_file", mock_download),
            patch("services.audio_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/audio")
            assert response.status_code == 200
            full_url = response.json()
            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.target_audio_path.lstrip('/')}"
            assert full_url == expected_url
    finally:
        app.dependency_overrides.clear()


def test_brick_audio_cache_miss_downloads_and_caches(client, tmp_path):
    """On cache miss: DB brick is read, file is downloaded from S3, cached in Redis with TTL."""
    brick = _setup_test_brick(learner_id=1)
    learner = Learner(id=1, name="Test Learner")

    cache_key = f"{BRICK_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.delete(cache_key)

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"AUDIO_DATA_TEST")

    mock_download.side_effect = fake_download

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.audio_cache_service.download_file", mock_download),
            patch("services.audio_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/audio")
            assert response.status_code == 200
            full_url = response.json()

            # 1. Full URL returned
            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.target_audio_path.lstrip('/')}"
            assert full_url == expected_url

            # 2. File downloaded to local cache
            saved_file = tmp_path / brick.target_audio_path
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"AUDIO_DATA_TEST"
            assert mock_download.call_count == 1

            # 3. Redis entry created with 1-day TTL
            assert redis.exists(cache_key)
            ttl = redis.ttl(cache_key)
            assert 86300 <= ttl <= 86400
            assert redis.get(cache_key) == brick.target_audio_path
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_brick_audio_cache_hit_returns_immediately(client, tmp_path):
    """On cache hit with local file present: returns full URL without re-downloading from S3."""
    brick = _setup_test_brick(learner_id=1)
    learner = Learner(id=1, name="Test Learner")

    cache_key = f"{BRICK_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.setex(cache_key, 86400, brick.target_audio_path)

    # Local file already exists
    local_file = tmp_path / brick.target_audio_path
    local_file.parent.mkdir(parents=True, exist_ok=True)
    local_file.write_bytes(b"EXISTING_AUDIO")

    mock_download = MagicMock()

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.audio_cache_service.download_file", mock_download),
            patch("services.audio_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/audio")
            assert response.status_code == 200
            full_url = response.json()

            expected_url = f"{settings.asset_base_url.rstrip('/')}/{brick.target_audio_path.lstrip('/')}"
            assert full_url == expected_url
            # S3 download must NOT be called on cache hit
            mock_download.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_brick_audio_cache_hit_repairs_missing_local_file(client, tmp_path):
    """If Redis has a cache hit but local file was deleted, it repairs/downloads it from S3."""
    brick = _setup_test_brick(learner_id=1)
    learner = Learner(id=1, name="Test Learner")

    cache_key = f"{BRICK_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.setex(cache_key, 86400, brick.target_audio_path)

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"REPAIRED_AUDIO")

    mock_download.side_effect = fake_download

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.audio_cache_service.download_file", mock_download),
            patch("services.audio_cache_service.ASSETS_DIR", tmp_path),
        ):
            response = client.get(f"/api/bricks/{brick.id}/audio")
            assert response.status_code == 200

            # File repaired
            saved_file = tmp_path / brick.target_audio_path
            assert saved_file.exists()
            assert saved_file.read_bytes() == b"REPAIRED_AUDIO"
            assert mock_download.call_count == 1
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)


def test_cleanup_expired_audio_files(tmp_path):
    """Files not in Redis cache are deleted from the local directory."""
    assets_dir = tmp_path
    target_dir = assets_dir / "system-brick-audios"
    target_dir.mkdir(parents=True, exist_ok=True)

    redis = get_redis_client()

    # Active file: has Redis entry -> keep
    active_file = target_dir / "active.wav"
    active_file.write_bytes(b"ACTIVE")
    redis.setex(
        f"{AUDIO_CATCH_PREFIX}system-brick-audios/active.wav", 86400, "1"
    )

    # Expired file: no Redis entry -> delete
    expired_file = target_dir / "expired.wav"
    expired_file.write_bytes(b"EXPIRED")
    redis.delete(f"{AUDIO_CATCH_PREFIX}system-brick-audios/expired.wav")

    with patch("services.audio_cache_service.ASSETS_DIR", assets_dir):
        deleted = cleanup_expired_audio_files(directory=target_dir)

        assert str(expired_file) in deleted
        assert not expired_file.exists()
        assert active_file.exists()

    redis.delete(f"{AUDIO_CATCH_PREFIX}system-brick-audios/active.wav")


def test_forced_align_unauthenticated_fails(client):
    """Accessing forced alignment without authentication should fail (401)."""
    response = client.get("/api/audio/forced-alignment/1")
    assert response.status_code == 401


def test_forced_align_not_belonging_to_learner_fails(client):
    """Accessing forced alignment for a brick of another learner returns 404."""
    brick = _setup_test_brick(learner_id=1)

    other_learner = Learner(id=999, name="Other Learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        other_learner
    )

    try:
        response = client.get(f"/api/audio/forced-alignment/{brick.id}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_forced_align_caches_and_aligns(client, tmp_path):
    """On cache miss, forced_align downloads/caches audio and calls inference align."""
    brick = _setup_test_brick(learner_id=1)
    learner = Learner(id=1, name="Test Learner")

    cache_key = f"{BRICK_CACHE_PREFIX}{brick.id}"
    redis = get_redis_client()
    redis.delete(cache_key)

    mock_download = MagicMock()

    def fake_download(s3_key, local_path):
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"AUDIO_DATA_FOR_ALIGN")

    mock_download.side_effect = fake_download

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "segments": [
            {"word": "Hello", "start_sec": 0.0, "end_sec": 0.5},
        ]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    try:
        with (
            patch("services.audio_cache_service.download_file", mock_download),
            patch("services.audio_cache_service.ASSETS_DIR", tmp_path),
            patch("http_client.get_client", return_value=mock_client),
        ):
            response = client.get(f"/api/audio/forced-alignment/{brick.id}")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["word"] == "Hello"
            assert data[0]["start_sec"] == 0.0
            assert data[0]["end_sec"] == 0.5

            # Verified audio file downloaded to local cache
            saved_file = tmp_path / brick.target_audio_path
            assert saved_file.exists()

            # Verified cached in Redis
            assert redis.get(cache_key) == brick.target_audio_path

            # Verified alignment payload
            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert call_kwargs[0][0] == "/audio/align"
            assert call_kwargs[1]["json"]["transcript"] == brick.target_text
            assert (
                brick.target_audio_path in call_kwargs[1]["json"]["audio_url"]
            )
    finally:
        app.dependency_overrides.clear()
        redis.delete(cache_key)
