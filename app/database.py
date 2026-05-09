import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from mutagen import File as MutagenFile
from pydantic import EmailStr
from sqlalchemy import CheckConstraint, event
from sqlalchemy.engine import Engine
from sqlmodel import (
    Field,
    Relationship,
    Session,
    SQLModel,
    create_engine,
    select,
    text,
)

from schemas.cefr import CEFR_MAPPING, CEFRLevel

from . import security
from .config import settings
from .schemas import (
    GrammarPoint,
    InteractionType,
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
    snippet_interactions: list["SnippetInteraction"] = Relationship(
        back_populates="learner"
    )
    historyanswerquestions: list["HistoryAnswerQuestion"] = Relationship(back_populates="learners")
    thetalearnerlessons: list["ThetaLearnerLesson"] = Relationship(back_populates="learner")

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
    target_audio_path: str
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
    target_audio_path: str | None = None
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
    user_target_audio_path: str | None = None
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


class Snippet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content: str
    audio_path: str
    creator_id: int = Field(default=None, foreign_key="learner.id")
    creator: Learner = Relationship()
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    is_public: bool = True
    translation: str | None = None  # for dynamic translation

    # for feature enhancement later
    log_frequency: float | None = None
    audio_duration: float | None = None

    interactions: list["SnippetInteraction"] = Relationship(
        back_populates="snippet"
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
        default_factory=lambda: datetime.now(timezone.utc)
    )

    learner_id: int | None = Field(default=None, foreign_key="learner.id")
    learner: "Learner" = Relationship(back_populates="snippet_interactions")
    snippet: "Snippet" = Relationship(back_populates="interactions")


class SnippetLike(SQLModel, table=True):
    learner_id: int = Field(foreign_key="learner.id", primary_key=True)
    snippet_id: int = Field(foreign_key="snippet.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
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
    thetalearnerlessons: list["ThetaLearnerLesson"] = Relationship(back_populates="lesson")



# Concept (Core node)
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


# Concept Relation (Graph)
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
    questions: list["Question"] = Relationship(back_populates="exercise")



class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    content: str | None = None
    question: str | None = None
    answer: str | None = None
    correct_answer: str | None = None

    type: str | None = None
    score: float | None = None
    difficulty: float | None = Field(default=0.0)
    exercise_id: int = Field(default=None, foreign_key="exercise.id")
    exercise: Exercise | None = Relationship(back_populates="questions")
    historyanswerquestions: list["HistoryAnswerQuestion"] = Relationship(back_populates="questions")


class Example(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sentence: str
    explanation: str | None = None
    concept_id: int | None = Field(default=None, foreign_key="concept.id")
    concept: Concept | None = Relationship(back_populates="examples")

class HistoryAnswerQuestion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    question_id: int = Field(foreign_key="question.id")
    user_answer: str | None = None
    timesecond: datetime | None = None 
    questions : Question = Relationship(back_populates="historyanswerquestions")
    learners : Learner = Relationship(back_populates="historyanswerquestions")

class ThetaLearnerLesson(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    lesson_id: int = Field(foreign_key="lesson.id")
    theta: float | None = Field(default=0)

    lesson: Lesson | None = Relationship(back_populates="thetalearnerlessons")
    learner: Learner | None = Relationship(back_populates="thetalearnerlessons")



sqlite_url = f"sqlite:///{settings.db_path}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()

    # for SQLite only
    # enable foreign key restrictions
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def init_db():
    """
    Create the tables an insert data to them if the database does not exits.
    """
    if not os.path.exists(settings.db_path):
        print(f"{settings.db_path} not found, create a new one.")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            session.exec(
                text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS brick_search USING fts5( 
                    brick_id UNINDEXED, 
                    target_text, 
                    native_text, 
                    tokenize="porter unicode61" 
                );
            """)
            )
            session.exec(
                text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS snippet_search USING fts5( 
                    snippet_id UNINDEXED, 
                    content, 
                    tokenize="porter unicode61" 
                );
            """)
            )
            print("Database schema created.")
            create_brick_triggers(session)
            create_snippet_triggers(session)
            init_bricks(session)
            init_snippets(session)
            init_from_attach_dbs(session)
        transfer_knowledge_graph_data()

        print("Done initialize table data.")
    else:
        print(f"{settings.db_path} already exists, skip initialization.")


def delete_db():
    db_path = Path(settings.db_path)
    if db_path.exists():
        db_path.unlink()
        print(f"Deleted {db_path}.")
    else:
        print(f"WARNING: Trying to delete a non existing {db_path}.")


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

        group_name = CEFR_MAPPING[group_name]

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
                target_audio_path=str(
                    Path("brick-audios") / row["source_audio_path"]
                ),
                cefr_level=row["cefr_level"],
                collections=[],
                creator=initial_account.learner,
                brick_metadata=brick_metadata,
            )
            collection.bricks.append(brick)

        session.add(collection)
    print("Bricks imported!")
    session.commit()


def create_brick_triggers(session: Session):
    # Trigger for NEW bricks
    session.exec(
        text("""
        CREATE TRIGGER IF NOT EXISTS trg_brick_insert AFTER INSERT ON brick
        BEGIN
            INSERT INTO brick_search (brick_id, target_text, native_text)
            VALUES (new.id, new.target_text, new.native_text);
        END;
    """)
    )

    # Trigger for UPDATED bricks
    session.exec(
        text("""
        CREATE TRIGGER IF NOT EXISTS trg_brick_update AFTER UPDATE ON brick
        BEGIN
            UPDATE brick_search 
            SET target_text = new.target_text, 
                native_text = new.native_text
            WHERE brick_id = old.id;
        END;
    """)
    )

    # Trigger for DELETED bricks
    session.exec(
        text("""
        CREATE TRIGGER IF NOT EXISTS trg_brick_delete AFTER DELETE ON brick
        BEGIN
            DELETE FROM brick_search WHERE brick_id = old.id;
        END;
    """)
    )
    session.commit()


def create_snippet_triggers(session: Session):
    # Trigger for NEW snippets
    session.exec(
        text("""
        CREATE TRIGGER IF NOT EXISTS trg_snippet_insert AFTER INSERT ON snippet
        BEGIN
            INSERT INTO snippet_search (snippet_id, content)
            VALUES (new.id, new.content);
        END;
    """)
    )

    session.commit()


def init_snippets(session: Session):
    COMMON_VOICE_DIR = Path(settings.snippets_folder)

    def import_common_voice(csv_name: str, creator_id: int = 1):
        df = pd.read_csv(COMMON_VOICE_DIR / csv_name)
        split = csv_name.replace(".csv", "")
        snippets = []

        for row in df.to_dict("records"):
            audio_path = COMMON_VOICE_DIR / split / row["filename"]
            # Get duration in seconds
            audio_info = MutagenFile(audio_path).info
            duration_seconds = audio_info.length
            snippets.append(
                Snippet(
                    content=row["text"],
                    audio_path=str(audio_path),
                    creator_id=creator_id,
                    log_frequency=text_service.log_frequency(row["text"]),
                    audio_duration=duration_seconds,
                )
            )

        session.add_all(snippets)
        session.commit()

        print(f"{len(snippets)} Snippets was imported from {csv_name}")

    import_common_voice("cv-valid-test.csv")


def init_from_attach_dbs(session: Session):
    session.exec(
        text(
            f"ATTACH DATABASE '{settings.ytb_subtitle_db_path}' AS subtitle_db"
        )
    )
    print(f"Attached {settings.ytb_subtitle_db_path}")

def transfer_knowledge_graph_data():
    engine_old = create_engine(
        f"sqlite:///{BASE_DIR}/knowledge_graph.db", echo=False
    )
    dict_mapping = {
        "topic": Topic,
        "lesson": Lesson,
        "exercise": Exercise,
        "question": Question,
    }

    with Session(engine_old) as session_old:
        all_data = {}
        for table_name, model in dict_mapping.items():
            # Đọc raw, không dùng ORM
            rows = session_old.exec(text(f"SELECT * FROM {table_name}")).all()
            columns = session_old.exec(text(f"PRAGMA table_info({table_name})")).all()
            col_names = [col[1] for col in columns]
            all_data[table_name] = [dict(zip(col_names, row)) for row in rows]

    with Session(engine) as session_new:
        try:
            for table_name, model in dict_mapping.items():
                valid_fields = model.model_fields.keys()
                for data in all_data[table_name]:
                    filtered = {k: v for k, v in data.items() if k in valid_fields}
                    session_new.add(model(**filtered))
            session_new.commit()
            print("Knowledge graph data transferred successfully.")
        except Exception as e:
            session_new.rollback()
            raise e