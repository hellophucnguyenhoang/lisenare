from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import EmailStr
from sqlalchemy import DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint, text

from app.config import settings


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=20)
    hashed_password: str = Field(max_length=100)
    email: EmailStr | None = Field(
        default=None, index=True, unique=True, max_length=254
    )
    last_login_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    learner_id: int = Field(
        foreign_key="learner.id", unique=True, ondelete="CASCADE"
    )

    # Have to use `Optional` instead of `"Learner" | None` here
    learner: Optional["Learner"] = Relationship(back_populates="account")


class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    native_text: str = Field(
        max_length=settings.brick_max_words * settings.brick_avg_word_len
    )
    target_text: str = Field(
        max_length=settings.brick_max_words * settings.brick_avg_word_len
    )
    target_audio_path: str = Field(max_length=settings.max_path_len)
    target_pron: str | None = Field(
        default=None,
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
    )
    context: str | None = Field(
        default=None, max_length=settings.context_max_chars
    )
    unit_type: str  # 'word' or 'sentence'
    is_private: bool = True
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    collection_id: int = Field(
        foreign_key="collection.id", ondelete="CASCADE", index=True
    )
    collection: "Collection" = Relationship(back_populates="bricks")

    creator_id: int = Field(
        foreign_key="learner.id", ondelete="CASCADE", index=True
    )
    creator: "Learner" = Relationship(back_populates="bricks")

    memories: list["BrickMemory"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )
    reviews: list["BrickReview"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )


class BrickMemory(SQLModel, table=True):
    """
    Stores the LATEST algorithmic memory state for a brick.
    Exactly ONE row exists per learner-brick pair. Updated on every review.
    """

    id: int | None = Field(default=None, primary_key=True)

    learner_id: int = Field(
        foreign_key="learner.id", ondelete="CASCADE", index=True
    )
    learner: "Learner" = Relationship(back_populates="memories")

    brick_id: int = Field(
        foreign_key="brick.id", ondelete="CASCADE", index=True
    )
    brick: Brick = Relationship(back_populates="memories")

    fsrs_card_dict: dict = Field(default={}, sa_type=JSONB)
    due: datetime = Field(sa_type=DateTime(timezone=True), index=True)

    last_reviewed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )


class Collection(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "creator_id", "name", name="uq_creator_collection_name"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    description: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    creator_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    creator: "Learner" = Relationship(back_populates="collections")

    bricks: list[Brick] | None = Relationship(
        back_populates="collection", cascade_delete=True
    )


class Learner(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)

    account: Account | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    collections: list[Collection] | None = Relationship(
        back_populates="creator", cascade_delete=True
    )
    bricks: list[Brick] | None = Relationship(
        back_populates="creator", cascade_delete=True
    )
    tags: list["Tag"] | None = Relationship(
        back_populates="creator", cascade_delete=True
    )
    memories: list[BrickMemory] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    reviews: list["BrickReview"] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    audio_contributions: list["SnippetAudioContribution"] | None = (
        Relationship(back_populates="learner", cascade_delete=True)
    )
    snippets: list["Snippet"] | None = Relationship(
        back_populates="creator", cascade_delete=True
    )
    snippet_reports: list["SnippetReport"] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    snippet_interactions: list["SnippetInteraction"] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )


class LearnerSetting(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    fsrs_weights: list[float] | None = Field(default=None, sa_type=JSONB)
    target_retention: float = Field(default=0.9)


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


class BrickReview(SQLModel, table=True):
    """
    Stores the immutable historical log of an individual review attempt.
    Appends a new row every time a learner answers.
    """

    id: int | None = Field(default=None, primary_key=True)
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    learner_id: int = Field(
        foreign_key="learner.id", ondelete="CASCADE", index=True
    )
    learner: Learner = Relationship(back_populates="reviews")

    brick_id: int = Field(
        foreign_key="brick.id", ondelete="CASCADE", index=True
    )
    brick: Brick = Relationship(back_populates="reviews")

    # Performance metrics for this specific attempt
    first_score: float
    is_answer_revealed: bool = False

    # Again = 1, Hard = 2, Good = 3, Easy = 4
    fsrs_rating: int = Field(ge=1, le=4)
    fsrs_log_dict: dict = Field(default={}, sa_type=JSONB)

    # User's actual typed/spoken response payload for this attempt
    user_target_text: str | None = Field(
        default=None,
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
    )
    user_target_audio_path: str | None = Field(
        default=None, max_length=settings.max_path_len
    )


class Snippet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str = Field(
        max_length=settings.brick_max_words * settings.brick_avg_word_len
    )
    translation: str | None = Field(
        default=None,
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
    )
    content_audio_path: str | None = Field(
        default=None, max_length=settings.max_path_len
    )
    content_pron: str | None = Field(
        default=None,
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
    )
    context: str | None = Field(
        default=None, max_length=settings.context_max_chars
    )
    is_public: bool = True
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    creator_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    creator: Learner = Relationship(back_populates="snippets")

    audio_contributions: list["SnippetAudioContribution"] = Relationship(
        back_populates="snippet", cascade_delete=True
    )
    reports: list["SnippetReport"] = Relationship(
        back_populates="snippet", cascade_delete=True
    )
    interactions: list["SnippetInteraction"] = Relationship(
        back_populates="snippet", cascade_delete=True
    )


class SnippetAudioContribution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    audio_path: str = Field(max_length=settings.max_path_len)
    status: str = Field(default="pending")  # approved, pending, rejected
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    snippet_id: int = Field(foreign_key="snippet.id", ondelete="CASCADE")
    snippet: Snippet = Relationship(back_populates="audio_contributions")

    learner_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    learner: Learner = Relationship(back_populates="audio_contributions")


class SnippetInteraction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # LISTEN, VIEW_TRANSLATION, LIKE, DISLIKE, REMOVE_REACTION, ADD
    type: str = Field(max_length=20)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    session_id: str

    snippet_id: int = Field(foreign_key="snippet.id", ondelete="CASCADE")
    snippet: Snippet = Relationship(back_populates="interactions")

    learner_id: int | None = Field(
        default=None, foreign_key="learner.id", ondelete="CASCADE"
    )
    learner: Learner = Relationship(back_populates="snippet_interactions")


class SessionProfile(SQLModel, table=True):
    session_id: str = Field(primary_key=True)
    profile_vector: bytes
    interaction_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class SnippetReaction(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    snippet_id: int = Field(foreign_key="snippet.id", primary_key=True)
    reaction: str = Field(max_length=20)  # LIKE / DISLIKE
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class SnippetReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    reason: str = Field(default="No provided", max_length=1000)
    status: str = Field(default="open")  # open, resolved, dismissed
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    snippet_id: int = Field(foreign_key="snippet.id", ondelete="CASCADE")
    snippet: Snippet = Relationship(back_populates="reports")

    learner_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    learner: Learner = Relationship(back_populates="snippet_reports")


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=20)

    creator_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    creator: Learner | None = Relationship(back_populates="tags")


class Taggable(SQLModel, table=True):
    tag_id: int = Field(
        foreign_key="tag.id", primary_key=True, ondelete="CASCADE"
    )
    tag: "Tag" = Relationship()
    taggable_id: int = Field(primary_key=True, index=True)

    # 'Brick', 'Collection', 'Snippet',...
    taggable_type: str = Field(primary_key=True, max_length=20, index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


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
