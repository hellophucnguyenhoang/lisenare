from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import Learner, LearnerSetting, engine
from app.main import app
from app.services import auth_service


def test_get_learner_me(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None
        setting_in_db = session.get(LearnerSetting, 2)
        if not setting_in_db:
            setting_in_db = LearnerSetting(learner_id=2, practice_lang="en")
            session.add(setting_in_db)
            session.commit()
            session.refresh(setting_in_db)

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.get("/learners/me")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 2
    assert "name" in data
    assert data["practice_lang"] == "en"


def test_update_learner_practice_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch("/learners/me", json={"practice_lang": "ja"})
    assert response.status_code == 200
    data = response.json()
    assert data["practice_lang"] == "ja"

    # Verify directly in DB
    with Session(engine) as session:
        setting = session.get(LearnerSetting, 2)
        assert setting is not None
        assert setting.practice_lang == "ja"

        # Restore to en
        setting.practice_lang = "en"
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

    response = client.patch("/learners/me", json={"name": "Updated Name"})
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


def test_update_learner_both_name_and_practice_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None
        orig_name = learner_in_db.name

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    response = client.patch(
        "/learners/me", json={"name": "Bilingual Learner", "practice_lang": "fr"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bilingual Learner"
    assert data["practice_lang"] == "fr"

    # Verify and restore
    with Session(engine) as session:
        learner = session.get(Learner, 2)
        learner.name = orig_name
        setting = session.get(LearnerSetting, 2)
        if setting:
            setting.practice_lang = "en"
            session.add(setting)
        session.add(learner)
        session.commit()

    app.dependency_overrides.clear()


def test_update_learner_invalid_practice_lang(client: TestClient):
    with Session(engine) as session:
        learner_in_db = session.get(Learner, 2)
        assert learner_in_db is not None

    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        learner_in_db
    )

    # Too long
    response = client.patch("/learners/me", json={"practice_lang": "eng"})
    assert response.status_code == 422

    # Too short
    response = client.patch("/learners/me", json={"practice_lang": "e"})
    assert response.status_code == 422

    app.dependency_overrides.clear()
