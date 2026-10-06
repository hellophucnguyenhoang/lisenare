from sqlmodel import Field, SQLModel

from shared_constants import BRICK_AVG_WORD_LEN, BRICK_MAX_WORDS


class TTSRequest(SQLModel):
    text: str = Field(
        default="How are you?",
        max_length=BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN,
        description=f"Maximum {BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN} characters",
    )
    voice: str = Field(
        default="af_heart",
        description="Kokoro voice: 'af_heart' / 'am_adam' (English), 'jf_alpha' / 'jm_kumo' (Japanese)",
    )


class PhonemeAnalysisRequest(SQLModel):
    target_text: str = Field(description="Reference / target text")
    learner_text: str = Field(description="Learner transcribed / spoken text")
    lang: str = Field(
        default="en", description="Language code ('en', 'ja', etc.)"
    )


class PhonemeAnalysisResponse(SQLModel):
    teacher_phonemes: str = Field(
        description="Teacher/reference phonetic transcription"
    )
    learner_phonemes: str = Field(description="Learner phonetic transcription")
    normalized_teacher_text: str
    normalized_learner_text: str


class SpellFixRequest(SQLModel):
    text: str = Field(description="Sentence or text to correct spelling for")


class SpellFixResponse(SQLModel):
    corrected_text: str = Field(description="Spell-corrected sentence or text")


class TermNormalizeRequest(SQLModel):
    term: str = Field(description="Word or term to normalize and validate")


class TermNormalizeResponse(SQLModel):
    normalized_term: str = Field(
        description="Normalized word or closest match"
    )
    is_valid: bool = Field(
        description="Whether the term is a valid English word"
    )


class WordValidationRequest(SQLModel):
    word: str = Field(description="Word to validate")


class WordValidationResponse(SQLModel):
    is_valid: bool = Field(description="Whether the word is in the dictionary")


class StemmingRequest(SQLModel):
    text: str | list[str] = Field(
        description="Text or list of texts to extract stems for"
    )


class StemmingResponse(SQLModel):
    stems: list[str] = Field(description="List of unique extracted stems")


class LemmatizeRequest(SQLModel):
    text: str = Field(description="Text to lemmatize")


class LemmatizeResponse(SQLModel):
    lemmas: list[str] = Field(
        description="List of normalized unique lemmas from text"
    )


class RarityRequest(SQLModel):
    text: str = Field(
        description="Text or word to calculate lexical rarity for"
    )
    lang: str = Field(default="en", description="Language code")


class RarityResponse(SQLModel):
    rarity: float = Field(description="Lexical rarity score in range [0, 1]")
    log_frequency: float = Field(description="Log frequency of the text")


class BatchRarityRequest(SQLModel):
    texts: list[str] = Field(
        description="List of words or texts to calculate lexical rarity for"
    )
    lang: str = Field(default="en", description="Language code")


class BatchRarityResponse(SQLModel):
    rarities: list[float] = Field(description="List of lexical rarity scores")
