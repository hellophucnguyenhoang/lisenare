import io
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import Brick, Island, Learner, LearnerSetting, engine
from exceptions import ErrorCode
from main import app
from schemas import BrickExport
from services import auth_service
from services.brick_service import count_bricks_in_island
from services.island_service import import_island


def test_count_bricks_in_island_helper():
    with Session(engine) as session:
        col = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        assert col is not None
        assert count_bricks_in_island(session, col.id) == 1111


def test_create_brick_fails_when_island_full(client: TestClient):
    learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    with Session(engine) as session:
        full_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        assert full_island is not None
        full_island_id = full_island.id

    brick_payload = {
        "native_text": "Xin chào giới hạn",
        "target_text": "Limit test unique brick 1",
        "island_id": full_island_id,
        "tags": ["test"],
    }
    audio_file = io.BytesIO(b"fake audio data")

    try:
        with (
            patch(
                "utils.file_utils.save_upload_file",
                return_value=("mock/path.wav", None),
            ),
            patch("services.search_service.add_brick_embedding"),
        ):
            response = client.post(
                "/api/bricks",
                data={"json_data": json.dumps(brick_payload)},
                files={
                    "target_audio_file": ("audio.wav", audio_file, "audio/wav")
                },
            )

        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
        )
    finally:
        app.dependency_overrides.clear()


def test_update_brick_move_to_full_island_fails(client: TestClient):
    learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    with Session(engine) as session:
        avail_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 10"
            )
        ).first()
        full_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        assert avail_island is not None
        assert full_island is not None
        avail_island_id = avail_island.id
        full_island_id = full_island.id

    # Create brick in available island
    brick_payload = {
        "native_text": "Xin chào chuyển đảo",
        "target_text": "Move test unique brick 1",
        "island_id": avail_island_id,
    }
    audio_file = io.BytesIO(b"fake audio data")

    brick_id = None
    try:
        with (
            patch(
                "utils.file_utils.save_upload_file",
                return_value=("mock/path.wav", None),
            ),
            patch("services.search_service.add_brick_embedding"),
        ):
            response = client.post(
                "/api/bricks",
                data={"json_data": json.dumps(brick_payload)},
                files={
                    "target_audio_file": ("audio.wav", audio_file, "audio/wav")
                },
            )
            assert response.status_code == 200
            brick_id = response.json()["id"]

            # Try to move brick to full island
            move_res = client.patch(
                f"/api/bricks/{brick_id}",
                data={"json_data": json.dumps({"island_id": full_island_id})},
            )
            assert move_res.status_code == 400
            assert (
                move_res.json()["error_code"]
                == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
            )

            # Update same brick without changing island_id succeeds
            update_same_res = client.patch(
                f"/api/bricks/{brick_id}",
                data={
                    "json_data": json.dumps(
                        {
                            "island_id": avail_island_id,
                            "native_text": "Updated VN",
                        }
                    )
                },
            )
            assert update_same_res.status_code == 200
    finally:
        app.dependency_overrides.clear()
        if brick_id:
            with patch("services.search_service.remove_brick_embedding"):
                client.delete(f"/api/bricks/{brick_id}")


def test_add_brick_from_fails_when_target_island_full(client: TestClient):
    learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    with Session(engine) as session:
        full_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        source_brick = session.exec(
            select(Brick).where(Brick.is_private == False)  # noqa: E712
        ).first()
        assert full_island is not None
        assert source_brick is not None
        full_island_id = full_island.id
        source_brick_id = source_brick.id

    try:
        response = client.post(
            f"/api/bricks/add-from/{source_brick_id}",
            json={"island_id": full_island_id},
        )
        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
        )
    finally:
        app.dependency_overrides.clear()


def test_add_bricks_from_island_fails_when_target_island_full(
    client: TestClient,
):
    learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    with Session(engine) as session:
        full_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        source_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 10"
            )
        ).first()
        assert full_island is not None
        assert source_island is not None
        full_island_id = full_island.id
        source_island_id = source_island.id

    try:
        response = client.post(
            f"/api/bricks/add-from-island/{source_island_id}",
            json={"target_island_id": full_island_id},
        )
        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
        )
    finally:
        app.dependency_overrides.clear()


def test_add_bricks_from_island_fails_when_exceeding_capacity():
    from services.brick_service import add_bricks_from_island
    import pytest
    from exceptions import RequestException

    with Session(engine) as session:
        # Create a temporary learner, source island with 2 bricks, and target island
        src_learner = Learner(
            id=881, name="SrcLearner", setting=LearnerSetting()
        )
        tgt_learner = Learner(
            id=882, name="TgtLearner", setting=LearnerSetting()
        )
        session.add(src_learner)
        session.add(tgt_learner)
        session.flush()

        src_island = Island(name="SrcIsland", creator_id=src_learner.id)
        tgt_island = Island(name="TgtIsland", creator_id=tgt_learner.id)
        session.add(src_island)
        session.add(tgt_island)
        session.flush()

        b1 = Brick(
            native_text="N1",
            target_text="Unique_Cap_1",
            target_audio_path="test1.wav",
            kind="word",
            is_private=False,
            creator_id=src_learner.id,
            island_id=src_island.id,
        )
        b2 = Brick(
            native_text="N2",
            target_text="Unique_Cap_2",
            target_audio_path="test2.wav",
            kind="word",
            is_private=False,
            creator_id=src_learner.id,
            island_id=src_island.id,
        )
        session.add(b1)
        session.add(b2)
        session.commit()

        try:
            with patch(
                "services.brick_service.count_bricks_in_island",
                return_value=1110,
            ):
                with pytest.raises(RequestException) as exc_info:
                    add_bricks_from_island(
                        session=session,
                        source_island_id=src_island.id,
                        target_island_id=tgt_island.id,
                        learner_id=tgt_learner.id,
                    )
                assert exc_info.value.status_code == 400
                assert (
                    exc_info.value.detail["error_code"]
                    == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
                )
        finally:
            session.delete(b1)
            session.delete(b2)
            session.delete(src_island)
            session.delete(tgt_island)
            session.delete(src_learner)
            session.delete(tgt_learner)
            session.commit()


def test_import_island_fails_when_island_full(client: TestClient):
    learner = Learner(id=2, setting=LearnerSetting())
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner
    )

    with Session(engine) as session:
        full_island = session.exec(
            select(Island).where(
                Island.creator_id == 2, Island.name == "Island 1"
            )
        ).first()
        assert full_island is not None
        full_island_id = full_island.id

    import_payload = [
        {
            "native_text": "VN import",
            "target_text": "EN import unique 99",
            "target_audio_path": "system-brick-audios/test.wav",
            "kind": "sentence",
            "is_private": True,
            "target_lang": "en",
        }
    ]

    try:
        response = client.post(
            f"/api/islands/{full_island_id}/import",
            files={
                "file": (
                    "import.json",
                    json.dumps(import_payload).encode("utf-8"),
                    "application/json",
                )
            },
        )
        assert response.status_code == 400
        assert (
            response.json()["error_code"]
            == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
        )
    finally:
        app.dependency_overrides.clear()


def test_import_island_fails_when_exceeding_capacity():
    with Session(engine) as session:
        with patch(
            "services.island_service.count_bricks_in_island",
            return_value=1110,
        ):
            bricks_to_import = [
                BrickExport(
                    native_text="N1",
                    target_text="T_unique_limit_1",
                    target_audio_path="test1.wav",
                    kind="word",
                ),
                BrickExport(
                    native_text="N2",
                    target_text="T_unique_limit_2",
                    target_audio_path="test2.wav",
                    kind="word",
                ),
            ]
            import pytest
            from exceptions import RequestException

            with pytest.raises(RequestException) as exc_info:
                import_island(
                    session=session,
                    island_id=10,
                    learner_id=2,
                    bricks=bricks_to_import,
                )
            assert exc_info.value.status_code == 400
            assert (
                exc_info.value.detail["error_code"]
                == ErrorCode.ISLAND_BRICK_LIMIT_EXCEEDED.value
            )
