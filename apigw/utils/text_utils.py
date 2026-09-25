import math

import spacy
from wordfreq import word_frequency

import http_client
from shared_schemas.text import (
    SpellFixRequest,
    SpellFixResponse,
    StemmingRequest,
    StemmingResponse,
    TermNormalizeRequest,
    TermNormalizeResponse,
    WordValidationRequest,
    WordValidationResponse,
)

nlp = spacy.load("en_core_web_sm")


def log_frequency(text: str, lang="en") -> float:
    # Tokenize the sentence and get the frequency of every token,
    # then aggregate them using the Harmonic Mean
    # Formula: 1 / (1/f1 + 1/f2 + ...)
    content_freq = word_frequency(text, lang)
    return math.log10(content_freq + 1e-9)


def calculate_rarity(text: str, lang="en") -> float:
    """
    Calculate lexical rarity score of a text.

    Returns:
        float in range [0, 1]
        Higher means less common / rarer.
    """
    log_freq = log_frequency(text, lang)
    return -log_freq / 9


def lemmatize_to_set(text: str) -> set[str]:
    """
    Convert text into a set of normalized lemmas.
    """
    doc = nlp(text)

    lemmas = {token.lemma_.lower() for token in doc if token.is_alpha}

    return lemmas


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
