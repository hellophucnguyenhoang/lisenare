import os
import pandas as pd
import textstat
import string
from collections.abc import Iterator
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session
from datetime import datetime, timezone, timedelta
from pydantic import EmailStr
from pathlib import Path

from .config import settings
from .schemas import (
    LearnerAccountCreate,
    CEFRLevel,
    UnitType,
    SentenceStructure,
    SentenceFunction,
    GrammarPoint,
)
from . import security


class BrickMetadataGrammarPoint(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    brick_metadata_id: int | None = Field(
        default=None, foreign_key="brickmetadata.id"
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
    grammar_points: list[BrickMetadataGrammarPoint] = Relationship()


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


class CollectionBrick(SQLModel, table=True):
    collection_id: int | None = Field(
        default=None, foreign_key="collection.id", primary_key=True
    )
    brick_id: int | None = Field(
        default=None, foreign_key="brick.id", primary_key=True
    )


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
    bricks: list["Brick"] | None = Relationship(
        back_populates="collections", link_model=CollectionBrick
    )


class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    native_text: str
    target_text: str = Field(unique=True)
    target_audio_uri: str
    cefr_level: CEFRLevel
    is_public: bool = True
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="bricks")
    brick_metadata_id: int | None = Field(
        default=None, foreign_key="brickmetadata.id", unique=True
    )
    brick_metadata: BrickMetadata = Relationship()
    collections: list[Collection] = Relationship(
        back_populates="bricks", link_model=CollectionBrick
    )
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
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=settings.otp_expire_minutes)
    )
    used: bool = False


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
        print("Done creating table schema.")
        with Session(engine) as session:
            init_bricks(session)
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

    def compute_flesch_kincaid_grade(text: str):
        translator = str.maketrans("", "", string.punctuation)
        no_punct_text = text.translate(translator)
        score = textstat.flesch_kincaid_grade(no_punct_text)
        return round(score, 3)

    def extract_collection_data(collection_data: pd.DataFrame):
        # collection Name (Shortest text)
        shortest_text_idx = (
            collection_data["en_source_text"].str.len().idxmin()
        )
        collection_name = collection_data.loc[
            shortest_text_idx, "en_source_text"
        ]

        # group Name (Highest CEFR)
        ordered_levels = [level.value for level in CEFRLevel]

        # We find the maximum based on the order defined in the list above
        group_name = pd.Categorical(
            collection_data["cefr_level"],
            categories=ordered_levels,
            ordered=True,
        ).max()

        # difficulty score: Concat all text then calculate
        full_text = " ".join(collection_data["en_source_text"].astype(str))
        difficulty_score = compute_flesch_kincaid_grade(full_text)

        return collection_name, group_name, difficulty_score

    initial_learner_account_create = LearnerAccountCreate(
        full_name="Sam Nguyen",
        username="qwer",
        password="1234",
        email="nguyenphuc1234sonhoapy@gmail.com",
    )
    initial_account = create_learner_account(
        session, initial_learner_account_create
    )

    brick_metadata_df = pd.read_csv(
        os.path.join(settings.brick_folder, "metadata.csv")
    )
    for collection_id, collection_data in brick_metadata_df.groupby(
        "collection_id"
    ):
        # Create collection
        collection_name, group_name, difficulty_score = (
            extract_collection_data(collection_data)
        )
        collection = Collection(
            name=collection_name,
            group_name=group_name,
            difficulty_score=difficulty_score,
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
                target_audio_uri=row["source_audio_path"],
                cefr_level=CEFRLevel(row["cefr_level"]),
                collections=[],
                creator=initial_account.learner,
                brick_metadata=brick_metadata,
            )
            collection.bricks.append(brick)

        session.add(collection)

    session.commit()
