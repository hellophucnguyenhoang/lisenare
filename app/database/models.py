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
    target_lang: str = Field(
        default="en",
        max_length=2,
        index=True,
    )  # ISO 639-1 code
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

    interactions: list["BrickInteraction"] = Relationship(
        back_populates="brick", cascade_delete=True
    )
    memories: list["BrickMemory"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )
    reports: list["BrickReport"] = Relationship(
        back_populates="brick", cascade_delete=True
    )
    reviews: list["BrickReview"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )


class BrickInteraction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # LISTEN, LIKE, DISLIKE, REMOVE_REACTION, ADD
    type: str = Field(max_length=20)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    session_id: str

    brick_id: int = Field(foreign_key="brick.id", ondelete="CASCADE")
    brick: Brick = Relationship(back_populates="interactions")

    learner_id: int | None = Field(
        default=None, foreign_key="learner.id", ondelete="CASCADE"
    )
    learner: "Learner" = Relationship(back_populates="brick_interactions")


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

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class BrickReaction(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    brick_id: int = Field(foreign_key="brick.id", primary_key=True)
    reaction: str = Field(max_length=20)  # LIKE / DISLIKE
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


class BrickReport(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    reason: str = Field(default="No provided", max_length=1000)
    status: str = Field(default="open")  # open, resolved, dismissed
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    brick_id: int = Field(foreign_key="brick.id", ondelete="CASCADE")
    brick: Brick = Relationship(back_populates="reports")

    learner_id: int = Field(foreign_key="learner.id", ondelete="CASCADE")
    learner: "Learner" = Relationship(back_populates="brick_reports")


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
    learner: "Learner" = Relationship(back_populates="reviews")

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

    # Learner's actual typed/spoken response payload for this attempt
    learner_target_text: str | None = Field(
        default=None,
        max_length=settings.brick_max_words * settings.brick_avg_word_len,
    )
    learner_target_audio_path: str | None = Field(
        default=None, max_length=settings.max_path_len
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
    brick_interactions: list[BrickInteraction] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    brick_reports: list["BrickReport"] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    memories: list[BrickMemory] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    reviews: list["BrickReview"] | None = Relationship(
        back_populates="learner", cascade_delete=True
    )
    setting: "LearnerSetting" = Relationship(
        back_populates="learner", cascade_delete=True
    )
    tags: list["Tag"] | None = Relationship(
        back_populates="creator", cascade_delete=True
    )

    @property
    def practice_lang(self) -> str:
        try:
            return self.setting.practice_lang if self.setting else "en"
        except Exception:
            return "en"


class LearnerSetting(SQLModel, table=True):
    learner_id: int = Field(
        foreign_key="learner.id", primary_key=True, ondelete="CASCADE"
    )
    fsrs_weights: list[float] | None = Field(default=None, sa_type=JSONB)
    target_retention: float = Field(default=0.9)
    practice_lang: str = Field(default="en", max_length=2)  # ISO 639-1 code
    learner: "Learner" = Relationship(back_populates="setting")


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


class SessionProfile(SQLModel, table=True):
    session_id: str = Field(primary_key=True)
    profile_vector: bytes
    interaction_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )


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

    # 'Brick', 'Collection',...
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
