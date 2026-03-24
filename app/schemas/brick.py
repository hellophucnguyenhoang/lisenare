from sqlmodel import SQLModel
from datetime import datetime
from enum import Enum

from schemas.cefr import CEFRLevel


class UnitType(str, Enum):
    word = "word"
    phrase = "phrase"
    sentence = "sentence"


# ---------- Enums ----------
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


class BrickUpdate(SQLModel):
    native_text: str | None = None
    target_text: str | None = None
    cefr_level: CEFRLevel | None = None
    is_public: bool | None = None
    collection_ids: list[int] | None = None


class BrickContextSearch(SQLModel):
    native_text: str
    target_text: str
    target_audio_uri: str
    cefr_level: CEFRLevel
    is_public: bool = True


class BrickBase(SQLModel):
    native_text: str
    target_text: str
    target_audio_uri: str
    cefr_level: CEFRLevel
    is_public: bool = True
    creator_id: int


class BrickRead(BrickBase):
    id: int
    last_edit_at: datetime


class BrickCreate(BrickBase):
    pass


class BrickLearnRead(SQLModel):
    brick: BrickRead
    total_bricks: int
