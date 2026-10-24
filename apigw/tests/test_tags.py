import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from database import Island, Learner, LearnerSetting, engine
from main import app
from services import auth_service
from services.tag_service import (
    clean_tag,
    clean_tags,
    delete_tags_for_entity,
    fetch_tags_for_entity,
    set_tags_for_entity,
)


def test_clean_tag_basic():
    assert clean_tag("TAG") == "tag"
    assert clean_tag("hello world") == "helloworld"
    assert clean_tag("tag-name_123") == "tagname123"
    assert clean_tag("Special!@#$%^&*()Tags") == "specialtags"
    assert clean_tag("   ") == ""
    assert clean_tag("café 123") == "caf123"


def test_clean_tags_list():
    raw_tags = [
        "  HELLO  ",
        "world!",
        "hello",
        "tag-1, tag-2",
        "!!!",
        "   ",
        "Tag 2",
    ]
    cleaned = clean_tags(raw_tags)
    assert cleaned == ["hello", "world", "tag1", "tag2"]


def test_tag_service_set_and_delete():
    with Session(engine) as session:
        learner = session.exec(select(Learner).where(Learner.id == 2)).first()
        assert learner is not None

        # Set tags
        tags = set_tags_for_entity(
            session=session,
            entity_id=1,
            entity_type="TestEntity",
            tag_names=[" Tag ONE! ", "tag-TWO", "tag one"],
            creator_id=learner.id,
        )
        session.commit()
        assert tags == ["tagone", "tagtwo"]
        assert fetch_tags_for_entity(session, 1, "TestEntity") == [
            "tagone",
            "tagtwo",
        ]

        # Cleanup
        delete_tags_for_entity(session, 1, "TestEntity")
        session.commit()
        assert fetch_tags_for_entity(session, 1, "TestEntity") == []


def test_create_and_query_brick_with_uncleaned_tags(client: TestClient):
    fake_learner = Learner(id=2, setting=LearnerSetting(retrieval_lang="en"))
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with Session(engine) as session:
        col = session.exec(
            select(Island).where(Island.creator_id == 2)
        ).first()
        assert col is not None
        col_id = col.id

    try:
        # Create brick with dirty tags
        brick_payload = {
            "native_text": "Thử nghiệm thẻ",
            "target_text": "Tag test brick dirty",
            "island_id": col_id,
            "tags": ["  Dirty Tag #1! ", "EXTRA_TAG-2  ", "dirty tag 1"],
        }
        with (
            patch(
                "utils.file_utils.save_upload_file",
                return_value=("fake/path.wav", None),
            ),
            patch("services.search_service.add_brick_embedding"),
        ):
            response = client.post(
                "/api/bricks",
                data={"json_data": json.dumps(brick_payload)},
                files={"target_audio_file": ("a.wav", b"fake", "audio/wav")},
            )
        assert response.status_code == 200
        data = response.json()
        brick_id = data["id"]
        assert sorted(data["tags"]) == ["dirtytag1", "extratag2"]

        # Query using uncleaned tag param
        query_res = client.get("/api/bricks", params={"tags": "Dirty Tag #1!"})
        assert query_res.status_code == 200
        items = query_res.json()["items"]
        matching_ids = [item["id"] for item in items]
        assert brick_id in matching_ids

        # Update tags with dirty tags
        update_payload = {"tags": ["Updated_Tag #99"]}
        with patch(
            "utils.file_utils.save_upload_file",
            return_value=("fake/path.wav", None),
        ):
            update_res = client.patch(
                f"/api/bricks/{brick_id}",
                data={"json_data": json.dumps(update_payload)},
            )
        assert update_res.status_code == 200
        assert update_res.json()["tags"] == ["updatedtag99"]

    finally:
        app.dependency_overrides.clear()
        with patch("services.search_service.remove_brick_embedding"):
            client.delete(f"/api/bricks/{brick_id}")
