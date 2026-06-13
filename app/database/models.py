from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import CheckConstraint, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    text,
)

from app.config import settings
from app.schemas import (
    GrammarPoint,
    InteractionType,
    SentenceFunction,
    SentenceStructure,
    UnitType,
)
from schemas.cefr import CEFRLevel


class ExerciseType(str, Enum):
    REVIEW = "review"  # ôn tập
    PRACTICE = "practice"  # luyện tập


class BrickMetadataGrammarPoint(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    brick_metadata_id: int = Field(
        default=None, foreign_key="brickmetadata.id", ondelete="CASCADE"
    )
    grammar_point: GrammarPoint


class BrickMetadata(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
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
    grammar_points: list[BrickMetadataGrammarPoint] | None = Relationship(
        cascade_delete=True
    )


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str = Field(unique=True)
    email: EmailStr | None = Field(default=None, index=True, unique=True)
    last_login_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    learner_id: int = Field(foreign_key="learner.id", unique=True)
    learner: "Learner" = Relationship(back_populates="account")


class PushToken(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    last_sent_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    device_name: str | None = None
    last_ticket_id: str | None = None
    learner_id: int = Field(foreign_key="learner.id")
    learner: "Learner" = Relationship(back_populates="push_tokens")


class Learner(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    collections: list["Collection"] | None = Relationship(
        back_populates="creator"
    )
    bricks: list["Brick"] | None = Relationship(back_populates="creator")
    reviews: list["Review"] | None = Relationship(back_populates="learner")
    account: Account | None = Relationship(
        back_populates="learner"
    )  # Allow null in runtime
    brick_overrides: list["BrickOverride"] = Relationship(
        back_populates="learner"
    )
    snippet_interactions: list["SnippetInteraction"] = Relationship(
        back_populates="learner"
    )
    push_tokens: list["PushToken"] = Relationship(back_populates="learner")
    historyanswerquestions: list["HistoryAnswerQuestion"] = Relationship(
        back_populates="learners"
    )
    thetalearnerlessons: list["ThetaLearnerLesson"] = Relationship(
        back_populates="learner"
    )
    historychats: list["HistoryChat"] = Relationship(back_populates="learner")
    learner_exercises: list["LearnerExercise"] = Relationship(
        back_populates="learner"
    )


class LearnerSetting(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    fsrs_weights: list[float] | None = Field(default=None, sa_type=JSONB)
    target_retention: float = Field(default=0.9)


class Collection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="collections")

    bricks: list["Brick"] = Relationship(
        back_populates="collection", passive_deletes="all"
    )
    brick_overrides: list["BrickOverride"] = Relationship(
        back_populates="collection", cascade_delete=True
    )


class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    native_text: str
    target_text: str = Field(unique=True)
    target_audio_path: str
    cefr_level: CEFRLevel | None = None
    target_text_log_freq: float
    is_public: bool = True
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="bricks")

    brick_metadata_id: int | None = Field(
        default=None,
        foreign_key="brickmetadata.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
    )
    brick_metadata: BrickMetadata | None = Relationship(
        cascade_delete=True, sa_relationship_kwargs={"single_parent": True}
    )

    collection_id: int = Field(
        foreign_key="collection.id", ondelete="RESTRICT"
    )
    collection: Collection = Relationship(back_populates="bricks")

    reviews: list["Review"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )
    overrides: list["BrickOverride"] = Relationship(
        back_populates="brick", passive_deletes="all"
    )
    learning_cards: list["LearningCard"] = Relationship(
        back_populates="brick", cascade_delete=True
    )
    # System bricks only
    lesson_id: str | None = Field(default=None, index=True, nullable=True)
    __table_args__ = (
        Index(
            "idx_brick_search",
            text(
                "to_tsvector('simple', target_text || ' ' || native_text)"
            ),  # Use 'simple' or 'english'
            postgresql_using="gin",
        ),
    )


class BrickOverride(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    learner: Learner = Relationship(back_populates="brick_overrides")

    brick_id: int = Field(
        foreign_key="brick.id", primary_key=True, ondelete="RESTRICT"
    )
    brick: Brick = Relationship(back_populates="overrides")

    collection_id: int = Field(
        foreign_key="collection.id", primary_key=True, ondelete="CASCADE"
    )
    collection: Collection = Relationship(back_populates="brick_overrides")

    native_text: str | None = None
    target_audio_path: str | None = None
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    learner_id: int = Field(foreign_key="learner.id")
    learner: Learner = Relationship(back_populates="reviews")

    brick_id: int = Field(foreign_key="brick.id", ondelete="CASCADE")
    brick: Brick = Relationship(back_populates="reviews")

    first_score: float
    is_answer_revealed: bool = False
    fsrs_rating: int = Field(
        ge=1, le=4
    )  # Again = 1, Hard = 2, Good = 3, Easy = 4
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    fsrs_log_dict: dict = Field(default={}, sa_type=JSONB)
    user_target_text: str | None = None
    user_target_audio_path: str | None = None


class LearningCard(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)

    brick_id: int = Field(
        foreign_key="brick.id", primary_key=True, ondelete="CASCADE"
    )
    brick: "Brick" = Relationship(back_populates="learning_cards")

    fsrs_card_dict: dict = Field(default={}, sa_type=JSONB)
    due: datetime = Field(sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class OTP(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    hashed_code: str
    expires_at: datetime = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
            + timedelta(minutes=settings.otp_expire_minutes)
        ),
        sa_type=DateTime(timezone=True),
    )
    used: bool = False


class Snippet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    audio_path: str

    creator_id: int = Field(default=None, foreign_key="learner.id")
    creator: Learner = Relationship()

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    is_public: bool = True
    translation: str | None = None  # for dynamic translation

    # for feature enhancement later
    log_frequency: float | None = None
    audio_duration: float | None = None

    interactions: list["SnippetInteraction"] = Relationship(
        back_populates="snippet"
    )
    __table_args__ = (
        Index(
            "idx_snippet_search",
            text("to_tsvector('simple', content)"),
            postgresql_using="gin",
        ),
    )


class SnippetInteraction(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            """
            (type = 'TIME_SPENT' AND duration IS NOT NULL)
            OR
            (type != 'TIME_SPENT' AND duration IS NULL)
            """,
            name="check_duration_consistency",
        ),
    )
    id: int | None = Field(default=None, primary_key=True)

    session_id: str
    snippet_id: int = Field(foreign_key="snippet.id")

    type: InteractionType
    duration: float | None = None  # for TIME_SPENT

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    learner_id: int | None = Field(default=None, foreign_key="learner.id")
    learner: "Learner" = Relationship(back_populates="snippet_interactions")

    snippet: "Snippet" = Relationship(back_populates="interactions")


class SnippetReaction(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    snippet_id: int = Field(foreign_key="snippet.id", primary_key=True)
    reaction: str  # LIKE / DISLIKE
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class SessionProfile(SQLModel, table=True):
    session_id: str = Field(primary_key=True)
    profile_vector: bytes
    interaction_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class Topic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None

    lessons: list["Lesson"] = Relationship(back_populates="topic")


class Lesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None

    topic_id: int | None = Field(default=None, foreign_key="topic.id")
    topic: Topic | None = Relationship(back_populates="lessons")

    concepts: list["Concept"] = Relationship(back_populates="lesson")
    exercises: list["Exercise"] = Relationship(back_populates="lesson")
    thetalearnerlessons: list["ThetaLearnerLesson"] = Relationship(
        back_populates="lesson"
    )


class Concept(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    type: str  # grammar / pattern / word / usage / signal / rule
    description: str | None
    lesson_id: int = Field(default=None, foreign_key="lesson.id")
    lesson: Lesson | None = Relationship(back_populates="concepts")
    outgoing_relations: list["ConceptRelation"] = Relationship(
        back_populates="from_concept",
        sa_relationship_kwargs={
            "foreign_keys": "[ConceptRelation.from_concept_id]"
        },
    )

    incoming_relations: list["ConceptRelation"] = Relationship(
        back_populates="to_concept",
        sa_relationship_kwargs={
            "foreign_keys": "[ConceptRelation.to_concept_id]"
        },
    )

    # is_line_break: bool | None = None  # for formatting purposes
    examples: list["Example"] = Relationship(back_populates="concept")


class ConceptRelation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    from_concept_id: int = Field(foreign_key="concept.id")
    to_concept_id: int = Field(foreign_key="concept.id")

    relation_type: str | None  # uses, used_for, has_structure, similar_to...

    from_concept: Concept | None = Relationship(
        back_populates="outgoing_relations",
        sa_relationship_kwargs={
            "foreign_keys": "[ConceptRelation.from_concept_id]"
        },
    )

    to_concept: Concept | None = Relationship(
        back_populates="incoming_relations",
        sa_relationship_kwargs={
            "foreign_keys": "[ConceptRelation.to_concept_id]"
        },
    )


class Exercise(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    difficulty: float | None = Field(default=0.0)
    lesson_id: int = Field(default=None, foreign_key="lesson.id")
    lesson: Lesson | None = Relationship(back_populates="exercises")
    exercise_type: ExerciseType = ExerciseType.PRACTICE
    questions: list["Question"] = Relationship(back_populates="exercise")
    historychats: list["HistoryChat"] = Relationship(back_populates="exercise")
    learner_exercises: list["LearnerExercise"] = Relationship(
        back_populates="exercise"
    )


class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str | None = None
    question: str | None = None
    answer: str | None = None
    correct_answer: str | None = None

    type: str | None = None
    score: float | None = None
    difficulty: float | None = Field(default=0.0)
    last_difficulty_update_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    exercise_id: int = Field(default=None, foreign_key="exercise.id")
    exercise: Exercise | None = Relationship(back_populates="questions")
    historyanswerquestions: list["HistoryAnswerQuestion"] = Relationship(
        back_populates="questions"
    )


class Example(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sentence: str
    explanation: str | None = None
    concept_id: int | None = Field(default=None, foreign_key="concept.id")
    concept: Concept | None = Relationship(back_populates="examples")

class ThetaLearnerLesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    lesson_id: int = Field(foreign_key="lesson.id")
    theta: float | None = Field(default=0)
    is_completed: bool = Field(default=False)
    completed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )

    lesson: Lesson | None = Relationship(back_populates="thetalearnerlessons")
    learner: Learner | None = Relationship(
        back_populates="thetalearnerlessons"
    )


class LearnerExercise(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    exercise_id: int = Field(foreign_key="exercise.id", ondelete="CASCADE")
    num_correct_questions: int = Field(default=0)
    num_incorrect_questions: int = Field(default=0)
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    ended_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    is_completed: bool = Field(default=False)

    learner: Learner = Relationship(back_populates="learner_exercises")
    exercise: Exercise = Relationship(back_populates="learner_exercises")
    history_answer_questions: list["HistoryAnswerQuestion"] = Relationship(
        back_populates="learner_exercise"
    )

    __table_args__ = (
        Index(
            "ix_learnerexercise_learner_exercise",
            "learner_id",
            "exercise_id",
        ),
    )

class HistoryAnswerQuestion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    question_id: int = Field(foreign_key="question.id")
    user_answer: str | None = None
    timesecond: datetime | None = None
    learner_exercise_id: int | None = Field(
        default=None, foreign_key="learnerexercise.id"
    )
    questions: Question = Relationship(back_populates="historyanswerquestions")
    learners: Learner = Relationship(back_populates="historyanswerquestions")
    learner_exercise: LearnerExercise | None = Relationship(back_populates="history_answer_questions")

class YouTubeSubtitle(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    video_id: str = Field(index=True)  # The link to the video
    start: float
    duration: float
    transcript: str
    __table_args__ = (
        Index(
            "idx_ytb_search",
            text("to_tsvector('simple', transcript)"),
            postgresql_using="gin",
        ),
    )


class BrokenBrickReport(SQLModel, table=True):
    learner_id: int = Field(
        foreign_key="learner.id", primary_key=True, ondelete="CASCADE"
    )
    brick_id: int = Field(
        foreign_key="brick.id", primary_key=True, ondelete="CASCADE"
    )
    description: str | None = None
    reported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class HistoryChat(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="learner.id")
    learner: Learner | None = Relationship(back_populates="historychats")

    exercise_id: int = Field(foreign_key="exercise.id")
    exercise: Exercise | None = Relationship(back_populates="historychats")

    path_storage: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    modified_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class MistakeMemory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id", index=True)
    mistake_type: str
    content: str
    grammar_point: str | None = None
    suggested_fix: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class LearnerPreference(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    preferred_exercise_type: str | None = None
    learning_style: str | None = None
    goal: str | None = None
    notes: str | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class MistakeCache(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "normalized_answer",
            name="uq_mistakecache_qid_answer",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    normalized_answer: str
    mistake_type: str
    grammar_point: str | None = None
    explanation: str | None = None
    suggested_fix: str | None = None
    hit_count: int = Field(default=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

