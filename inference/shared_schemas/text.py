from pydantic import BaseModel, Field

from shared_constants import BRICK_AVG_WORD_LEN, BRICK_MAX_WORDS


class TTSRequest(BaseModel):
    text: str = Field(
        default="How are you?",
        max_length=BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN,
        description=f"Maximum {BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN} characters",
    )
    voice: str = Field(
        default="af_heart",
        description="Kokoro voice: 'af_heart' / 'am_adam' (English), 'jf_alpha' / 'jm_kumo' (Japanese)",
    )


class PhonemeAnalysisRequest(BaseModel):
    target_text: str = Field(description="Reference / target text")
    learner_text: str = Field(description="Learner transcribed / spoken text")
    lang: str = Field(
        default="en", description="Language code ('en', 'ja', etc.)"
    )


class PhonemeAnalysisResponse(BaseModel):
    teacher_phonemes: str = Field(
        description="Teacher/reference phonetic transcription"
    )
    learner_phonemes: str = Field(description="Learner phonetic transcription")
    normalized_teacher_text: str
    normalized_learner_text: str


class SpellFixRequest(BaseModel):
    text: str = Field(description="Sentence or text to correct spelling for")


class SpellFixResponse(BaseModel):
    corrected_text: str = Field(description="Spell-corrected sentence or text")


class TermNormalizeRequest(BaseModel):
    term: str = Field(description="Word or term to normalize and validate")


class TermNormalizeResponse(BaseModel):
    normalized_term: str = Field(
        description="Normalized word or closest match"
    )
    is_valid: bool = Field(
        description="Whether the term is a valid English word"
    )


class WordValidationRequest(BaseModel):
    word: str = Field(description="Word to validate")


class WordValidationResponse(BaseModel):
    is_valid: bool = Field(description="Whether the word is in the dictionary")


class StemmingRequest(BaseModel):
    text: str | list[str] = Field(
        description="Text or list of texts to extract stems for"
    )


class StemmingResponse(BaseModel):
    stems: list[str] = Field(description="List of unique extracted stems")


class LemmatizeRequest(BaseModel):
    text: str = Field(description="Text to lemmatize")


class LemmatizeResponse(BaseModel):
    lemmas: list[str] = Field(
        description="List of normalized unique lemmas from text"
    )


class RarityRequest(BaseModel):
    text: str = Field(
        description="Text or word to calculate lexical rarity for"
    )
    lang: str = Field(default="en", description="Language code")


class RarityResponse(BaseModel):
    rarity: float = Field(description="Lexical rarity score in range [0, 1]")
    log_frequency: float = Field(description="Log frequency of the text")


class BatchRarityRequest(BaseModel):
    texts: list[str] = Field(
        description="List of words or texts to calculate lexical rarity for"
    )
    lang: str = Field(default="en", description="Language code")


class BatchRarityResponse(BaseModel):
    rarities: list[float] = Field(description="List of lexical rarity scores")


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(description="List of texts to embed")
    lang: str = Field(
        default="en", description="Target language ('en', 'ja', etc.)"
    )
    is_query: bool = Field(
        default=False,
        description="Whether this is a query embedding (e.g. for asymmetric models like ruri)",
    )


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]] = Field(
        description="List of 384-dimensional embedding vectors"
    )
    model_version: str = Field(
        description="Identifier of the model used to generate embeddings"
    )
