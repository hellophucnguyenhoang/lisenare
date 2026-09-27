import http_client
from shared_schemas.text import (
    BatchRarityRequest,
    BatchRarityResponse,
    LemmatizeRequest,
    LemmatizeResponse,
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


def log_frequency(text: str, lang: str = "en") -> float:
    """Get log frequency of text via inference server."""
    response = http_client.get_client().post(
        "/text/rarity",
        json=RarityRequest(text=text, lang=lang).model_dump(mode="json"),
    )
    data = RarityResponse.model_validate(response.json())
    return data.log_frequency


def calculate_rarity(text: str, lang: str = "en") -> float:
    """
    Calculate lexical rarity score of a text via inference server.

    Returns:
        float in range [0, 1]
        Higher means less common / rarer.
    """
    response = http_client.get_client().post(
        "/text/rarity",
        json=RarityRequest(text=text, lang=lang).model_dump(mode="json"),
    )
    data = RarityResponse.model_validate(response.json())
    return data.rarity


def calculate_batch_rarity(texts: list[str], lang: str = "en") -> list[float]:
    """
    Calculate lexical rarity scores for a list of texts via inference server.
    """
    if not texts:
        return []
    response = http_client.get_client().post(
        "/text/batch-rarity",
        json=BatchRarityRequest(texts=texts, lang=lang).model_dump(
            mode="json"
        ),
    )
    data = BatchRarityResponse.model_validate(response.json())
    return data.rarities


def lemmatize_to_set(text: str) -> set[str]:
    """
    Convert text into a set of normalized lemmas via inference server.
    """
    if not text:
        return set()
    response = http_client.get_client().post(
        "/text/lemmatize",
        json=LemmatizeRequest(text=text).model_dump(mode="json"),
    )
    data = LemmatizeResponse.model_validate(response.json())
    return set(data.lemmas)


def get_lenient_stems(text: str | list[str]) -> set[str]:
    """
    Uses the aggressive Lancaster Stemmer on the inference server to ensure
    UK/US and tense variations match correctly.
    """
    if not text:
        return set()
    response = http_client.get_client().post(
        "/text/stemming",
        json=StemmingRequest(text=text).model_dump(mode="json"),
    )
    data = StemmingResponse.model_validate(response.json())
    return set(data.stems)


def normalize_target_term(word: str) -> tuple[str, bool]:
    response = http_client.get_client().post(
        "/text/normalize-term",
        json=TermNormalizeRequest(term=word).model_dump(mode="json"),
    )
    data = TermNormalizeResponse.model_validate(response.json())
    return data.normalized_term, data.is_valid


def is_valid_english(text: str) -> bool:
    response = http_client.get_client().post(
        "/text/validate-word",
        json=WordValidationRequest(word=text).model_dump(mode="json"),
    )
    data = WordValidationResponse.model_validate(response.json())
    return data.is_valid


def refined_spell_fix(sentence: str) -> str:
    response = http_client.get_client().post(
        "/text/spell-fix",
        json=SpellFixRequest(text=sentence).model_dump(mode="json"),
    )
    data = SpellFixResponse.model_validate(response.json())
    return data.corrected_text
