from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fsrs import Rating

from database import Learner
from main import app
from services import auth_service
from shared_schemas.sentence import SentenceCompareResponse
from shared_schemas.text import PhonemeAnalysisResponse


def test_create_brick_review_unauthenticated_fails():
    client = TestClient(app)
    response = client.post(
        "/api/brick-reviews",
        json={
            "brick_id": 1,
            "rating": 3,
        },
    )
    assert response.status_code == 401


def test_create_brick_review_authenticated_with_rating():
    client = TestClient(app)
    fake_learner = Learner(id=2, name="test_learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with patch(
        "services.brick_review_service.save_review", return_value=5
    ) as mock_save:
        response = client.post(
            "/api/brick-reviews",
            json={
                "brick_id": 10,
                "rating": 3,
                "first_score": 0.85,
                "is_answer_revealed": False,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total_reviews"] == 5
        assert mock_save.called
        review_arg = mock_save.call_args[1]["review_create"]
        assert review_arg.brick_id == 10
        assert review_arg.rating == Rating.Good
        assert review_arg.first_score == 0.85

    app.dependency_overrides.clear()


def test_create_brick_review_string_rating():
    client = TestClient(app)
    fake_learner = Learner(id=2, name="test_learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    with patch(
        "services.brick_review_service.save_review", return_value=12
    ) as mock_save:
        response = client.post(
            "/api/brick-reviews",
            json={
                "brick_id": 20,
                "rating": "easy",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total_reviews"] == 12
        assert mock_save.called
        review_arg = mock_save.call_args[1]["review_create"]
        assert review_arg.brick_id == 20
        assert review_arg.rating == Rating.Easy

    # Confirm /api/reviews does not exist (we picked /brick-reviews consistently)
    response_reviews_alias = client.post(
        "/api/reviews",
        json={"brick_id": 20, "rating": "easy"},
    )
    assert response_reviews_alias.status_code == 404

    app.dependency_overrides.clear()


def test_create_brick_review_missing_rating_fails():
    client = TestClient(app)
    fake_learner = Learner(id=2, name="test_learner")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    response = client.post(
        "/api/brick-reviews",
        json={
            "brick_id": 20,
            "first_score": 0.8,
        },
    )
    assert response.status_code == 422

    app.dependency_overrides.clear()


def test_sentence_comparison_does_not_save_review():
    client = TestClient(app)
    fake_learner = Learner(id=2, name="test_learner", retrieval_lang="en")
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        fake_learner
    )

    mock_semantic_resp = MagicMock()
    mock_semantic_resp.json.return_value = SentenceCompareResponse(
        score=0.9, correct=True
    ).model_dump(mode="json")

    mock_phoneme_resp = MagicMock()
    mock_phoneme_resp.json.return_value = PhonemeAnalysisResponse(
        teacher_phonemes="h eh l o",
        learner_phonemes="h eh l o",
        normalized_teacher_text="hello",
        normalized_learner_text="hello",
    ).model_dump(mode="json")

    def mock_post(url, **kwargs):
        if url == "/text/semantic-comparison":
            return mock_semantic_resp
        elif url == "/text/phoneme-analysis":
            return mock_phoneme_resp
        raise ValueError(f"Unexpected url {url}")

    with (
        patch("http_client.get_client") as mock_http,
        patch("services.brick_review_service.save_review") as mock_save_review,
    ):
        mock_http.return_value.post.side_effect = mock_post
        response = client.post(
            "/api/text/sentence-comparison",
            json={
                "sentence1": "hello",
                "sentence2": "hello",
                "review_base": {"brick_id": 1, "is_answer_revealed": False},
            },
        )
        assert response.status_code == 200
        assert response.json()["score"] == 1.0
        # save_review must NOT be called anymore
        assert not mock_save_review.called

    app.dependency_overrides.clear()
