from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from constants import (
    CONTEXT_MAX_CHARS,
    MAX_PATH_LEN,
    OTP_EXPIRE_MINUTES,
    SEMANTIC_EMB_DIM,
)
from shared_constants import BRICK_AVG_WORD_LEN, BRICK_MAX_WORDS


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "account"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(
        String(254),
        unique=True,
        index=True,
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE"),
        unique=True,
    )

    learner: Mapped["Learner"] = relationship(back_populates="account")


class Brick(Base):
    __tablename__ = "brick"
    id: Mapped[int] = mapped_column(primary_key=True)
    native_text: Mapped[str] = mapped_column(
        String(BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN)
    )
    target_text: Mapped[str] = mapped_column(
        String(BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN)
    )
    target_audio_path: Mapped[str] = mapped_column(String(MAX_PATH_LEN))

    # ISO 639-1 code, 'en', 'ja'.
    target_lang: Mapped[str] = mapped_column(
        String(2),
        default="en",
        index=True,
    )
    target_pron: Mapped[str | None] = mapped_column(String(CONTEXT_MAX_CHARS))

    context: Mapped[str | None] = mapped_column(String(CONTEXT_MAX_CHARS))
    image_path: Mapped[str | None] = mapped_column(String(MAX_PATH_LEN))

    kind: Mapped[str] = mapped_column(String)  # 'word' or 'sentence'
    is_private: Mapped[bool] = mapped_column(default=True)
    is_skipped: Mapped[bool] = mapped_column(default=False)

    last_edit_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    island_id: Mapped[int] = mapped_column(
        ForeignKey("island.id", ondelete="CASCADE"),
        index=True,
    )
    island: Mapped["Island"] = relationship(back_populates="bricks")

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE"),
        index=True,
    )
    creator: Mapped["Learner"] = relationship(back_populates="bricks")

    embedding_id: Mapped[int | None] = mapped_column(
        ForeignKey("text_embedding.id", ondelete="RESTRICT"),
        index=True,
    )
    embedding: Mapped[Optional["TextEmbedding"]] = relationship(
        back_populates="bricks"
    )

    interactions: Mapped[list["BrickInteraction"]] = relationship(
        back_populates="brick",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    memories: Mapped[list["BrickMemory"]] = relationship(
        back_populates="brick",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["BrickReport"]] = relationship(
        back_populates="brick",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reviews: Mapped[list["BrickReview"]] = relationship(
        back_populates="brick",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class BrickInteraction(Base):
    __tablename__ = "brickinteraction"

    id: Mapped[int] = mapped_column(primary_key=True)

    # LISTEN, ADD
    type: Mapped[str] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    session_id: Mapped[str] = mapped_column(String)

    brick_id: Mapped[int] = mapped_column(
        ForeignKey("brick.id", ondelete="CASCADE")
    )
    brick: Mapped[Brick] = relationship(back_populates="interactions")

    learner_id: Mapped[int | None] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE")
    )
    learner: Mapped[Optional["Learner"]] = relationship(
        back_populates="brick_interactions"
    )


class BrickMemory(Base):
    """
    Stores the LATEST algorithmic memory state for a brick.
    Exactly ONE row exists per learner-brick pair. Updated on every review.
    """

    __tablename__ = "brickmemory"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "brick_id",
            name="uq_brickmemory_learner_brick",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    fsrs_card_dict: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_skipped: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE"),
        index=True,
    )
    learner: Mapped["Learner"] = relationship(back_populates="memories")

    brick_id: Mapped[int] = mapped_column(
        ForeignKey("brick.id", ondelete="CASCADE"),
        index=True,
    )
    brick: Mapped[Brick] = relationship(back_populates="memories")


class BrickReport(Base):
    __tablename__ = "brickreport"

    id: Mapped[int] = mapped_column(primary_key=True)
    reason: Mapped[str] = mapped_column(String(1000), default="Not provided")

    # open, resolved, dismissed
    status: Mapped[str] = mapped_column(String, default="open")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    brick_id: Mapped[int] = mapped_column(
        ForeignKey("brick.id", ondelete="CASCADE")
    )

    brick: Mapped[Brick] = relationship(back_populates="reports")

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE")
    )
    learner: Mapped["Learner"] = relationship(back_populates="brick_reports")


class BrickReview(Base):
    """
    Stores the immutable historical log of an individual review attempt.
    Appends a new row every time a learner answers.
    """

    __tablename__ = "brickreview"
    __table_args__ = (
        CheckConstraint(
            "fsrs_rating >= 1 AND fsrs_rating <= 4",
            name="ck_brickreview_fsrs_rating",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE"),
        index=True,
    )
    learner: Mapped["Learner"] = relationship(back_populates="reviews")

    brick_id: Mapped[int] = mapped_column(
        ForeignKey("brick.id", ondelete="CASCADE"),
        index=True,
    )
    brick: Mapped[Brick] = relationship(back_populates="reviews")

    # Performance metrics for this specific attempt
    first_score: Mapped[float] = mapped_column()
    is_answer_revealed: Mapped[bool] = mapped_column(default=False)

    # Again = 1, Hard = 2, Good = 3, Easy = 4
    fsrs_rating: Mapped[int] = mapped_column()
    fsrs_log_dict: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Learner's actual typed/spoken response payload for this attempt
    learner_target_text: Mapped[str | None] = mapped_column(
        String(BRICK_MAX_WORDS * BRICK_AVG_WORD_LEN)
    )
    learner_target_audio_path: Mapped[str | None] = mapped_column(
        String(MAX_PATH_LEN)
    )


class Island(Base):
    __tablename__ = "island"

    __table_args__ = (
        UniqueConstraint(
            "creator_id",
            "name",
            name="uq_creator_island_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE")
    )
    creator: Mapped["Learner"] = relationship(back_populates="islands")

    # passive_deletes=True is for if the parent (island) is unloaded,
    # SQLAlchemy doesn't issue a SELECT to emit the DELETE statements to the children (bricks).
    bricks: Mapped[list[Brick]] = relationship(
        back_populates="island",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Learner(Base):
    __tablename__ = "learner"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    avatar_path: Mapped[str | None] = mapped_column(
        String(MAX_PATH_LEN),
        default="default-images/meo.webp",
    )

    account: Mapped[Account | None] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    islands: Mapped[list[Island]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bricks: Mapped[list[Brick]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brick_interactions: Mapped[list[BrickInteraction]] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brick_reports: Mapped[list[BrickReport]] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    memories: Mapped[list[BrickMemory]] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reviews: Mapped[list[BrickReview]] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    setting: Mapped["LearnerSetting"] = relationship(
        back_populates="learner",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    tags: Mapped[list["Tag"]] = relationship(
        back_populates="creator",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def retrieval_lang(self) -> str:
        return self.setting.retrieval_lang if self.setting else "en"


class LearnerSetting(Base):
    __tablename__ = "learnersetting"

    learner_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE"),
        primary_key=True,
    )

    fsrs_weights: Mapped[list[float] | None] = mapped_column(
        JSONB, default=None
    )
    target_retention: Mapped[float] = mapped_column(default=0.9)
    retrieval_lang: Mapped[str] = mapped_column(String(2), default="en")

    learner: Mapped[Learner] = relationship(back_populates="setting")


class OTP(Base):
    __tablename__ = "otp"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String)
    hashed_code: Mapped[str] = mapped_column(String)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: (
            datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
        ),
    )
    used: Mapped[bool] = mapped_column(default=False)


class SessionProfile(Base):
    __tablename__ = "sessionprofile"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_vector: Mapped[bytes] = mapped_column(LargeBinary)
    interaction_count: Mapped[int] = mapped_column(default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))

    creator_id: Mapped[int] = mapped_column(
        ForeignKey("learner.id", ondelete="CASCADE")
    )
    creator: Mapped[Learner] = relationship(back_populates="tags")


class Taggable(Base):
    __tablename__ = "taggable"
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag: Mapped[Tag] = relationship()

    taggable_id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 'Brick', 'Island',...
    taggable_type: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class TextEmbedding(Base):
    __tablename__ = "text_embedding"

    __table_args__ = (
        UniqueConstraint(
            "target_lang",
            "model_version",
            "content_hash",
            name="uq_text_embedding_content",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    target_lang: Mapped[str] = mapped_column(String(2))
    model_version: Mapped[str] = mapped_column(String(100))

    # SHA-256 digest of the canonical text.
    content_hash: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False
    )

    # Canonical text used to generate the embedding.
    source_text: Mapped[str] = mapped_column(String)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(SEMANTIC_EMB_DIM), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # passive_deletes="all" stops SQLAlchemy from setting the child records (bricks) foreign keys to NULL
    bricks: Mapped[list[Brick]] = relationship(
        back_populates="embedding",
        passive_deletes="all",
    )
