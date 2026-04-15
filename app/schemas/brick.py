from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from schemas.cefr import CEFRLevel

# ---------- Enums ----------


class UnitType(str, Enum):
    word = "word"
    phrase = "phrase"
    sentence = "sentence"


class SentenceStructure(str, Enum):
    simple = "simple"
    compound = "compound"
    complex = "complex"
    compound_complex = "compound_complex"


class SentenceFunction(str, Enum):
    declarative = "declarative"
    interrogative = "interrogative"
    imperative = "imperative"
    exclamatory = "exclamatory"


class GrammarPoint(str, Enum):
    # ---- sentence-level ----
    present_simple = "present_simple"
    present_continuous = "present_continuous"
    present_perfect = "present_perfect"
    past_simple = "past_simple"
    past_continuous = "past_continuous"
    past_perfect = "past_perfect"
    future_will = "future_will"
    future_going_to = "future_going_to"
    future_present_continuous = "future_present_continuous"
    modal = "modal"
    passive = "passive"
    conditional = "conditional"
    relative_clause = "relative_clause"
    comparison = "comparison"
    negation = "negation"
    question_form = "question_form"
    reason_result = "reason_result"
    time_sequence = "time_sequence"

    # ---- word-level ----
    noun = "noun"
    verb = "verb"
    adjective = "adjective"
    adverb = "adverb"
    preposition = "preposition"
    conjunction = "conjunction"
    pronoun = "pronoun"
    determiner = "determiner"

    # ---- phrase-level ----
    noun_phrase = "noun_phrase"
    verb_phrase = "verb_phrase"
    adjective_phrase = "adjective_phrase"
    adverb_phrase = "adverb_phrase"
    prepositional_phrase = "prepositional_phrase"


# ---------- Brick Metadata ----------


class BrickMetadataGrammarPointBase(SQLModel):
    grammar_point: GrammarPoint


class BrickMetadataGrammarPointCreate(BrickMetadataGrammarPointBase):
    pass


class BrickMetadataGrammarPointRead(BrickMetadataGrammarPointBase):
    id: int


class BrickMetadataBase(SQLModel):
    unit_type: UnitType = Field(
        default=UnitType.sentence,
        description="Type of brick unit: word, phrase, or sentence.",
    )
    structure: SentenceStructure | None = Field(
        default=None,
        description="Sentence structure (only for unit_type=sentence).",
    )
    function: SentenceFunction | None = Field(
        default=None,
        description="Communicative function (only for unit_type=sentence).",
    )


class BrickMetadataCreate(BrickMetadataBase):
    grammar_points: list[BrickMetadataGrammarPointCreate] | None = None


class BrickMetadataRead(BrickMetadataBase):
    id: int
    grammar_points: list[BrickMetadataGrammarPointRead] | None = None


# ---------- Brick ----------
class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    cefr_level: CEFRLevel | None = None
    is_public: bool | None = None
    collection_id: int | None = None
    brick_metadata: BrickMetadataCreate | None = None


class BrickContextSearch(SQLModel):
    brick_id: int
    native_text: str
    target_text: str


class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_audio_uri: str
    cefr_level: CEFRLevel | None = None
    is_public: bool = True
    creator_id: int
    collection_id: int | None = None


class BrickRead(BrickBase):
    id: int
    last_edit_at: datetime
    brick_metadata_id: int
    brick_metadata: BrickMetadataRead


class BrickReadSimple(SQLModel):
    id: int
    target_text: str


class BrickCreate(BrickBase):
    collection_name: str
    group_name: str


class BrickCreateRequest(SQLModel):
    native_text: str
    target_text: str
    is_public: bool = True
    collection_name: str = "my collection"
    group_name: str = "my group"
    brick_metadata: BrickMetadataCreate


class BrickLearnRead(SQLModel):
    brick: BrickRead
    total_bricks: int
