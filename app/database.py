import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from mutagen import File as MutagenFile
from pydantic import EmailStr
from sqlmodel import (
    Field,
    Relationship,
    Session,
    SQLModel,
    create_engine,
)

from . import security
from .config import settings
from .schemas import (
    CEFRLevel,
    GrammarPoint,
    LearnerAccountCreate,
    SentenceFunction,
    SentenceStructure,
    UnitType,
)
from .services import text_service


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
        default_factory=lambda: datetime.now(timezone.utc)
    )
    learner_id: int = Field(foreign_key="learner.id", unique=True)
    learner: "Learner" = Relationship(back_populates="account")


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
    post_interactions: list["PostInteraction"] = Relationship()


class Collection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    group_name: str = Field(
        default="my group",
        description="Used for grouping Collections into a group.",
    )
    difficulty_score: float
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="collections")
    bricks: list["Brick"] = Relationship(back_populates="collection")


class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    native_text: str
    target_text: str = Field(unique=True)
    target_audio_uri: str
    cefr_level: CEFRLevel | None = None
    is_public: bool = True
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="bricks")
    brick_metadata_id: int | None = Field(
        default=None,
        foreign_key="brickmetadata.id",
        unique=True,
        nullable=False,
    )
    brick_metadata: BrickMetadata | None = Relationship()
    collection_id: int | None = Field(
        default=None, foreign_key="collection.id"
    )
    collection: Collection | None = Relationship(back_populates="bricks")
    reviews: list["Review"] | None = Relationship(back_populates="brick")
    overrides: list["BrickOverride"] = Relationship(back_populates="brick")


class BrickOverride(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    brick_id: int = Field(foreign_key="brick.id", primary_key=True)
    native_text: str | None = None
    target_audio_uri: str | None = None
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    learner: Learner = Relationship(back_populates="brick_overrides")
    brick: Brick = Relationship(back_populates="overrides")


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    brick_id: int = Field(foreign_key="brick.id")
    first_score: float
    is_answer_revealed: bool = False
    fsrs_rating: int = Field(ge=1, le=4)
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user_target_text: str | None = None
    user_target_audio_uri: str | None = None
    brick: Brick = Relationship(back_populates="reviews")
    learner: Learner = Relationship(back_populates="reviews")


class LearningCard(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    brick_id: int = Field(foreign_key="brick.id", primary_key=True)
    fsrs_card_json: str
    due: datetime  # let due here for quick access


class OTP(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str
    hashed_code: str
    expires_at: datetime = Field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
            + timedelta(minutes=settings.otp_expire_minutes)
        )
    )
    used: bool = False


class Post(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    translation: str | None = None
    audio_uri: str
    log_frequency: float
    audio_duration: float
    accent: str | None = None
    creator_id: int = Field(default=None, foreign_key="learner.id")
    creator: Learner = Relationship()
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_public: bool = True
    post_interactions: list["PostInteraction"] = Relationship()


class PostInteraction(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    post_id: int = Field(foreign_key="post.id", primary_key=True)
    """
    {
        "dislike": -1.0,
        "view": -0.1,
        "like": 0.8,
        "save": 1.0,
    }
    """
    arm_feature: str
    reward: float | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


sqlite_url = f"sqlite:///{settings.db_url}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def init_db():
    """
    Create the tables an insert data to them if the database does not exits.
    """
    if not os.path.exists(settings.db_url):
        print(f"{settings.db_url} not found, create a new one.")
        SQLModel.metadata.create_all(engine)
        print("Database schema created.")
        with Session(engine) as session:
            init_bricks(session)
            init_posts(session)
        print("Done initialize table data.")
    else:
        print(f"{settings.db_url} already exits, skip initialization.")


def delete_db():
    db_url = Path(settings.db_url)
    if db_url.exists():
        db_url.unlink()
        print(f"Deleted {db_url}.")
    else:
        print(f"WARNING: Trying to delete a non existing {db_url}.")


def init_bricks(session: Session):
    def create_learner_account(
        session: Session, learner_account_create: LearnerAccountCreate
    ) -> Account:
        """
        This function is duplicated in the same function name
        in the accounts service to solve the circular import.
        """
        learner = Learner(full_name=learner_account_create.full_name)

        hashed_password = security.get_password_hash(
            learner_account_create.password
        )
        account = Account(
            username=learner_account_create.username,
            hashed_password=hashed_password,
            email=learner_account_create.email,
            learner=learner,
        )

        session.add(account)
        session.commit()
        session.refresh(account)
        return account

    def parse_enum(enum_cls, value):
        if pd.isna(value):
            return None
        return enum_cls(value)

    def parse_grammar_points(value):
        if pd.isna(value) or not value:
            return []
        return [
            BrickMetadataGrammarPoint(grammar_point=GrammarPoint(v))
            for v in str(value).split("|")
        ]

    def extract_collection_data(collection_data: pd.DataFrame):
        # collection Name (Shortest text)
        shortest_text_idx = (
            collection_data["en_source_text"].str.len().idxmin()
        )
        collection_name = collection_data.loc[
            shortest_text_idx, "en_source_text"
        ]

        ordered_levels = [level.name for level in CEFRLevel]

        # We find the maximum based on the order defined in the list above
        group_name = pd.Categorical(
            collection_data["cefr_level"],
            categories=ordered_levels,
            ordered=True,
        ).max()

        # Convert the group name "A2" into "Sơ cấp (A2)"
        group_name = CEFRLevel[group_name]

        # difficulty score: Concat all text then calculate
        full_text = " ".join(collection_data["en_source_text"].astype(str))
        log_frequency = text_service.log_frequency(full_text)

        return collection_name, group_name, log_frequency

    initial_learner_account_create = LearnerAccountCreate()
    initial_account = create_learner_account(
        session, initial_learner_account_create
    )

    me_account = LearnerAccountCreate(
        full_name="Nguyễn Hoàng Phúc",
        username="prhrurcr09",
        password="kcmtl5cM#",
        email="nguyenphuc1234sonhoapy@gmail.com",
    )
    create_learner_account(session, me_account)

    brick_metadata_df = pd.read_csv("metadata.csv")
    for collection_id, collection_data in brick_metadata_df.groupby(
        "collection_id"
    ):
        # Create collection
        collection_name, group_name, log_frequency = extract_collection_data(
            collection_data
        )
        collection = Collection(
            name=collection_name,
            group_name=group_name,
            difficulty_score=log_frequency,
            creator=initial_account.learner,
        )
        # Create brick and add to collection
        for _, row in collection_data.iterrows():
            brick_metadata = BrickMetadata(
                unit_type=parse_enum(UnitType, row["unit_type"]),
                structure=parse_enum(SentenceStructure, row["structure"]),
                function=parse_enum(SentenceFunction, row["function"]),
                grammar_points=parse_grammar_points(row["grammar_points"]),
            )
            brick = Brick(
                native_text=row["vi_translation"],
                target_text=row["en_source_text"],
                target_audio_uri=str(
                    Path("brick-audios") / row["source_audio_path"]
                ),
                cefr_level=CEFRLevel[row["cefr_level"]],
                collections=[],
                creator=initial_account.learner,
                brick_metadata=brick_metadata,
            )
            collection.bricks.append(brick)

        session.add(collection)
    print("Bricks imported!")
    session.commit()


def init_posts(session: Session):
    COMMON_VOICE_DIR = Path("common-voice")

    def import_common_voice(csv_name: str, creator_id: int = 1):
        df = pd.read_csv(COMMON_VOICE_DIR / csv_name)
        split = csv_name.replace(".csv", "")
        posts = []

        for row in df.to_dict("records"):
            audio_path = COMMON_VOICE_DIR / split / row["filename"]
            # Get duration in seconds
            audio_info = MutagenFile(audio_path).info
            duration_seconds = audio_info.length
            posts.append(
                Post(
                    content=row["text"],
                    audio_uri=str(audio_path),
                    log_frequency=text_service.log_frequency(row["text"]),
                    audio_duration=duration_seconds,
                    accent=row["accent"] if pd.notna(row["accent"]) else None,
                    creator_id=creator_id,
                )
            )

        session.add_all(posts)
        session.commit()

        print(f"{len(posts)} posts imported from {csv_name}")

    import_common_voice("cv-valid-test.csv")
