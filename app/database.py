import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from mutagen import File as MutagenFile
from pydantic import EmailStr
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import (
    Field,
    Relationship,
    Session,
    SQLModel,
    create_engine,
    select
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
BASE_DIR = Path(__file__).resolve().parent.parent


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
    bricks: list["Brick"] = Relationship(
        back_populates="collection", passive_deletes="all"
    )
    brick_overrides: list["BrickOverride"] = Relationship(
        back_populates="collection", passive_deletes="all"
    )


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
        ondelete="CASCADE",
    )
    brick_metadata: BrickMetadata | None = Relationship(
        cascade_delete=True, sa_relationship_kwargs={"single_parent": True}
    )
    collection_id: int | None = Field(
        default=None, foreign_key="collection.id", ondelete="RESTRICT"
    )
    collection: Collection | None = Relationship(back_populates="bricks")
    reviews: list["Review"] | None = Relationship(
        back_populates="brick", cascade_delete=True
    )
    overrides: list["BrickOverride"] = Relationship(
        back_populates="brick", passive_deletes="all"
    )
    learning_cards: list["LearningCard"] = Relationship(
        back_populates="brick", cascade_delete=True
    )


class BrickOverride(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    learner: Learner = Relationship(back_populates="brick_overrides")

    brick_id: int = Field(
        foreign_key="brick.id", primary_key=True, ondelete="RESTRICT"
    )
    brick: Brick = Relationship(back_populates="overrides")

    collection_id: int | None = Field(
        default=None, foreign_key="collection.id", ondelete="RESTRICT"
    )
    collection: Collection | None = Relationship(
        back_populates="brick_overrides"
    )

    native_text: str | None = None
    target_audio_uri: str | None = None
    last_edit_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    brick_id: int = Field(foreign_key="brick.id", ondelete="CASCADE")
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
    brick_id: int = Field(
        foreign_key="brick.id", primary_key=True, ondelete="CASCADE"
    )
    brick: "Brick" = Relationship(back_populates="learning_cards")
    fsrs_card_json: str
    due: datetime


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

# =========================
# Topic
# =========================
class Topic(SQLModel, table=True):
    id: int| None = Field(default=None, primary_key=True)
    name: str
    description: str | None

    lessons: list["Lesson"] = Relationship(back_populates="topic")


# =========================
# Lesson
# =========================
class Lesson(SQLModel, table=True):
    id: int| None = Field(default=None, primary_key=True)
    name: str
    description: str | None

    topic_id: int| None = Field(default=None, foreign_key="topic.id")
    topic: Topic|None = Relationship(back_populates="lessons")

    concepts: list["Concept"] = Relationship(back_populates="lesson")
    exercises: list["Exercise"] = Relationship(back_populates="lesson")


# =========================
# Concept (Core node)
# =========================
class Concept(SQLModel, table=True):
    id: int| None = Field(default=None, primary_key=True)
    name: str
    type: str  # grammar / pattern / word / usage / signal / rule
    description: str | None 
    lesson_id: int = Field(default=None, foreign_key="lesson.id")
    lesson: Lesson|None = Relationship(back_populates="concepts")
    outgoing_relations: list["ConceptRelation"] = Relationship(
        back_populates="from_concept",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.from_concept_id]"},
    )

    incoming_relations: list["ConceptRelation"] = Relationship(
        back_populates="to_concept",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.to_concept_id]"},
    )

    # is_line_break: Optional[bool] = None  # for formatting purposes
    examples: list["Example"] = Relationship(back_populates="concept")


# =========================
# Concept Relation (Graph)
# =========================
class ConceptRelation(SQLModel, table=True):
    id: int| None = Field(default=None, primary_key=True)

    from_concept_id: int = Field(foreign_key="concept.id")
    to_concept_id: int = Field(foreign_key="concept.id")

    relation_type: str | None  # uses, used_for, has_structure, similar_to...

    from_concept: Concept|None = Relationship(
        back_populates="outgoing_relations",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.from_concept_id]"},
    )

    to_concept: Concept|None = Relationship(
        back_populates="incoming_relations",
        sa_relationship_kwargs={"foreign_keys": "[ConceptRelation.to_concept_id]"},
    )


# =========================
# Exercise
# =========================
class Exercise(SQLModel, table=True):
    id: int |None = Field(default=None, primary_key=True)
    name: str

    lesson_id: int = Field(default=None, foreign_key="lesson.id")
    lesson: Lesson|None = Relationship(back_populates="exercises")

    questions: list["Question"] = Relationship(back_populates="exercise")


# =========================
# Question
# =========================
class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    content: str | None = None
    question: str | None = None
    answer: str | None = None
    correct_answer: str | None = None

    type: str | None = None
    score: float | None = None
    difficulty: float = 0.0
    exercise_id: int  = Field(default=None, foreign_key="exercise.id")
    exercise: Exercise |None = Relationship(back_populates="questions")


# =========================
# Example (sentence)
# =========================
class Example(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sentence: str
    explanation: str | None = None
    concept_id: int | None = Field(default=None, foreign_key="concept.id")
    concept: Concept | None = Relationship(back_populates="examples")

sqlite_url = f"sqlite:///{settings.db_url}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # for SQLite only
    cursor.close()


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
        transfer_knowledge_graph_data()

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

        # Extract the CEFRLevel.group_name enum
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

def transfer_knowledge_graph_data():
    engine_old = create_engine(f"sqlite:///{BASE_DIR}/knowledge_graph.db", echo=False)
    dict_mapping = {
        "topic": Topic,
        "lesson": Lesson,
        "exercise": Exercise,
        "question": Question,

    }
    with Session(engine_old) as session_old:
        all_data = {}
        for table_name, model in dict_mapping.items():
            all_data[table_name] = [r.model_dump() for r in session_old.exec(select(model)).all()]

    with Session(engine) as session_new:
        try:
            for table_name, model in dict_mapping.items():
                for data in all_data[table_name]:
                    session_new.add(model(**data))
            session_new.commit()
            print("Knowledge graph data transferred successfully.")
        except Exception as e:
            session_new.rollback()
            raise e
