from fastapi.testclient import TestClient

from main import app
from shared_schemas.text import (
    BatchRarityRequest,
    BatchRarityResponse,
    LemmatizeRequest,
    LemmatizeResponse,
    PhonemeAnalysisRequest,
    PhonemeAnalysisResponse,
    RarityRequest,
    RarityResponse,
    SpellFixRequest,
    SpellFixResponse,
    StemmingRequest,
    StemmingResponse,
    TermNormalizeRequest,
    TermNormalizeResponse,
    WordValidationRequest,
    WordValidationResponse,
)


def test_phoneme_analysis_endpoint():
    client = TestClient(app)
    req = PhonemeAnalysisRequest(
        target_text="It costs $5",
        learner_text="It costs 5 dollars",
    )
    response = client.post(
        "/text/phoneme-analysis", json=req.model_dump(mode="json")
    )
    assert response.status_code == 200
    data = PhonemeAnalysisResponse.model_validate(response.json())
    assert data.normalized_teacher_text == "It costs 5 dollars"
    assert data.normalized_learner_text == "It costs 5 dollars"
    assert data.teacher_phonemes.strip() != ""
    assert data.learner_phonemes.strip() != ""
    assert data.teacher_phonemes == data.learner_phonemes


def test_japanese_phoneme_analysis_endpoint():
    client = TestClient(app)
    req = PhonemeAnalysisRequest(
        target_text="美味しい鳥",
        learner_text="おいしいとり",
        lang="ja",
    )
    response = client.post(
        "/text/phoneme-analysis", json=req.model_dump(mode="json")
    )
    assert response.status_code == 200
    data = PhonemeAnalysisResponse.model_validate(response.json())
    assert data.teacher_phonemes == "oishiitori"
    assert data.learner_phonemes == "oishiitori"
    assert data.teacher_phonemes == data.learner_phonemes


def test_spell_fix_endpoints():
    client = TestClient(app)
    req = SpellFixRequest(text="thiss is a testt")
    response = client.post("/text/spell-fix", json=req.model_dump(mode="json"))
    assert response.status_code == 200
    data = SpellFixResponse.model_validate(response.json())
    assert data.corrected_text == "this is a test"


def test_normalize_term_endpoint():
    client = TestClient(app)

    # Valid exact match
    req_exact = TermNormalizeRequest(term="apple")
    res_exact = client.post(
        "/text/normalize-term", json=req_exact.model_dump(mode="json")
    )
    assert res_exact.status_code == 200
    data_exact = TermNormalizeResponse.model_validate(res_exact.json())
    assert data_exact.normalized_term == "apple"
    assert data_exact.is_valid is True

    # Typo correction
    req_typo = TermNormalizeRequest(term="appl")
    res_typo = client.post(
        "/text/normalize-term", json=req_typo.model_dump(mode="json")
    )
    assert res_typo.status_code == 200
    data_typo = TermNormalizeResponse.model_validate(res_typo.json())
    assert data_typo.normalized_term in ["apple", "apply"]
    assert data_typo.is_valid is True

    # Non-English / invalid
    req_invalid = TermNormalizeRequest(term="xyznonexistentword123")
    res_invalid = client.post(
        "/text/normalize-term", json=req_invalid.model_dump(mode="json")
    )
    assert res_invalid.status_code == 200
    data_invalid = TermNormalizeResponse.model_validate(res_invalid.json())
    assert data_invalid.is_valid is False


def test_validate_word_endpoints():
    client = TestClient(app)

    # Valid English word
    req_valid = WordValidationRequest(word="hello")
    res_valid = client.post(
        "/text/validate-word", json=req_valid.model_dump(mode="json")
    )
    assert res_valid.status_code == 200
    data_valid = WordValidationResponse.model_validate(res_valid.json())
    assert data_valid.is_valid is True

    # Invalid word
    req_invalid = WordValidationRequest(word="nonexistentxyz")
    res_invalid = client.post(
        "/text/validate-word", json=req_invalid.model_dump(mode="json")
    )
    assert res_invalid.status_code == 200
    data_invalid = WordValidationResponse.model_validate(res_invalid.json())
    assert data_invalid.is_valid is False


def test_stemming_endpoint():
    client = TestClient(app)

    # Test single string
    req_str = StemmingRequest(text="The dogs are running and playing")
    res_str = client.post(
        "/text/stemming", json=req_str.model_dump(mode="json")
    )
    assert res_str.status_code == 200
    data_str = StemmingResponse.model_validate(res_str.json())
    stems_set = set(data_str.stems)
    assert "dog" in stems_set
    assert "run" in stems_set
    assert "play" in stems_set

    # Test list of strings
    req_list = StemmingRequest(text=["running quickly", "played games"])
    res_list = client.post(
        "/text/stemming", json=req_list.model_dump(mode="json")
    )
    assert res_list.status_code == 200
    data_list = StemmingResponse.model_validate(res_list.json())
    stems_list_set = set(data_list.stems)
    assert "run" in stems_list_set
    assert "play" in stems_list_set

    # Test empty input
    req_empty = StemmingRequest(text="")
    res_empty = client.post(
        "/text/stemming", json=req_empty.model_dump(mode="json")
    )
    assert res_empty.status_code == 200
    data_empty = StemmingResponse.model_validate(res_empty.json())
    assert data_empty.stems == []


def test_lemmatize_endpoint():
    client = TestClient(app)
    req = LemmatizeRequest(text="The striped bats are hanging on feet")
    res = client.post("/text/lemmatize", json=req.model_dump(mode="json"))
    assert res.status_code == 200
    data = LemmatizeResponse.model_validate(res.json())
    lemmas_set = set(data.lemmas)
    assert "bat" in lemmas_set
    assert "foot" in lemmas_set
    assert "hang" in lemmas_set


def test_rarity_endpoint():
    client = TestClient(app)

    # Common word should have lower rarity
    req_common = RarityRequest(text="the", lang="en")
    res_common = client.post(
        "/text/rarity", json=req_common.model_dump(mode="json")
    )
    assert res_common.status_code == 200
    data_common = RarityResponse.model_validate(res_common.json())
    assert 0.0 <= data_common.rarity <= 1.0

    # Rare word should have higher rarity
    req_rare = RarityRequest(text="antediluvian", lang="en")
    res_rare = client.post(
        "/text/rarity", json=req_rare.model_dump(mode="json")
    )
    assert res_rare.status_code == 200
    data_rare = RarityResponse.model_validate(res_rare.json())
    assert 0.0 <= data_rare.rarity <= 1.0

    assert data_rare.rarity > data_common.rarity


def test_batch_rarity_endpoint():
    client = TestClient(app)
    req = BatchRarityRequest(texts=["the", "antediluvian", "hello"], lang="en")
    res = client.post("/text/batch-rarity", json=req.model_dump(mode="json"))
    assert res.status_code == 200
    data = BatchRarityResponse.model_validate(res.json())
    assert len(data.rarities) == 3
    # Common word rarer than "antediluvian"
    assert data.rarities[1] > data.rarities[0]
