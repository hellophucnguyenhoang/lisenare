from sqlmodel import SQLModel, Field
from .brick import GrammarPoint, UnitType, SentenceStructure, SentenceFunction


class BrickMetadataGrammarPointBase(SQLModel):
    grammar_point: GrammarPoint


class BrickMetadataGrammarPointCreate(BrickMetadataGrammarPointBase):
    pass


class BrickMetadataGrammarPointRead(BrickMetadataGrammarPointBase):
    id: int


class BrickMetadataBase(SQLModel):
    unit_type: UnitType = Field(
        description="Type of brick unit: word, phrase, or sentence."
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


class BrickMetadataPublic(BrickMetadataBase):
    id: int
    grammar_points: list[BrickMetadataGrammarPointRead] = []
