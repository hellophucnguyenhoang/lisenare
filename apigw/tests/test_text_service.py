from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from database.models import Learner, LearnerSetting
from main import app
from services import auth_service
from services.text_service import text_service
from shared_schemas.sentence import SentenceCompareResponse
from shared_schemas.text import PhonemeAnalysisResponse


def test_evaluate_phoneme_pronunciation_english():
    # Exact match
    res = text_service.evaluate_phoneme_pronunciation(
        "k æ t", "k æ t", lang="en"
    )
    assert res["accuracy_score"] == 1.0
    assert len(res["analysis"]) == 3
    assert all(a["status"] == "correct" for a in res["analysis"])

    # Partial / mispronounced
    res2 = text_service.evaluate_phoneme_pronunciation(
        "k æ t", "k ɛ t", lang="en"
    )
    assert 0.0 < res2["accuracy_score"] < 1.0
    assert any(a["status"] == "mispronounced" for a in res2["analysis"])


def test_evaluate_phoneme_pronunciation_japanese():
    # 100% Match (e.g. tori vs tori from kanji vs hiragana)
    res = text_service.evaluate_phoneme_pronunciation(
        "tori", "tori", lang="ja"
    )
    assert res["accuracy_score"] == 1.0
    assert all(a["status"] == "correct" for a in res["analysis"])

    # Partial match (watashihatorigasukidesu vs watashihainugasukidesu)
    res_partial = text_service.evaluate_phoneme_pronunciation(
        "watashihatorigasukidesu", "watashihainugasukidesu", lang="ja"
    )
    # difflib ratio is ~0.8889
    assert res_partial["accuracy_score"] == 0.8889


def test_sentence_comparison_japanese_endpoint(client: TestClient):
    mock_learner = Learner(
        id=1,
        name="Test Learner",
        setting=LearnerSetting(learner_id=1, practice_lang="ja"),
    )
    app.dependency_overrides[auth_service.decode_token_get_learner] = lambda: (
        mock_learner
    )

    with patch("http_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock semantic comparison (which might return low score for Japanese)
        mock_semantic_resp = MagicMock()
        mock_semantic_resp.json.return_value = SentenceCompareResponse(
            score=0.4, correct=False, threshold=0.7
        ).model_dump(mode="json")

        # Mock phoneme analysis response from inference service
        mock_phoneme_resp = MagicMock()
        mock_phoneme_resp.json.return_value = PhonemeAnalysisResponse(
            teacher_phonemes="oishiitori",
            learner_phonemes="oishiitori",
            normalized_teacher_text="美味しい鳥",
            normalized_learner_text="おいしいとり",
        ).model_dump(mode="json")

        def mock_post(url, **kwargs):
            if url == "/text/semantic-comparison":
                return mock_semantic_resp
            elif url == "/text/phoneme-analysis":
                # Ensure lang="ja" was passed
                payload = kwargs.get("json", {})
                assert payload.get("lang") == "ja"
                return mock_phoneme_resp
            raise ValueError(f"Unexpected url {url}")

        mock_client.post.side_effect = mock_post

        # Test request with Japanese sentences (auto-detects ja)
        response = client.post(
            "/api/text/sentence-comparison",
            json={
                "sentence1": "おいしいとり",
                "sentence2": "美味しい鳥",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 1.0
        assert data["correct"] is True

        # Test request with explicit lang="ja"
        response2 = client.post(
            "/api/text/sentence-comparison",
            json={
                "sentence1": "おいしいとり",
                "sentence2": "美味しい鳥",
                "lang": "ja",
            },
        )
        assert response2.status_code == 200
        assert response2.json()["score"] == 1.0

    app.dependency_overrides.clear()
