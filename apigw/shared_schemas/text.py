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


class PhonemeAnalysisResponse(SQLModel):
    teacher_ipa: str
    learner_ipa: str
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
