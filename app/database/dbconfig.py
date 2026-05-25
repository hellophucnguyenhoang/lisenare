from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect
from sqlmodel import (
    Session,
    SQLModel,
    create_engine,
    select,
    text,
)

from app import security
from app.config import settings
from app.schemas import (
    GrammarPoint,
    LearnerAccountCreate,
    SentenceFunction,
    SentenceStructure,
    UnitType,
)
from schemas.cefr import CEFR_MAPPING
from utils import text_utils

from .models import (
    Account,
    Brick,
    BrickMetadata,
    BrickMetadataGrammarPoint,
    Collection,
    Exercise,
    Learner,
    Lesson,
    Question,
    Snippet,
    Topic,
    YouTubeSubtitle,
)

engine = create_engine(settings.database_url, echo=False)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def init_db():
    """
    Create the tables an insert data to them if the database does not exits.
    """
    # Use SQLAlchemy to check if tables exist
    inspector = inspect(engine)
    if not inspector.has_table("snippet"):
        print("Database tables not found, creating schema...")

        # Create SQLModel tables
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Enable Extensions
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            init_bricks(session)
            init_snippets(session)
            session.commit()

        transfer_knowledge_graph_data()
        transfer_subtitles()
        print("Data initialization complete except embeddings.")
    else:
        print("Database already initialized, skipping.")


def delete_db():
    # 1. Drop the LangChain-managed tables (which SQLModel doesn't know about)
    with Session(engine) as session:
        session.exec(
            text("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;")
        )
        session.exec(
            text("DROP TABLE IF EXISTS langchain_pg_collection CASCADE;")
        )
        session.commit()

    # 2. Drop SQLModel tables
    SQLModel.metadata.drop_all(engine)
    print("Dropped all tables (including LangChain tables) from PostgreSQL.")


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

    initial_learner_account_create = LearnerAccountCreate()
    system_account = create_learner_account(
        session, initial_learner_account_create
    )

    me_account = LearnerAccountCreate(
        full_name="Phúc",
        username="prhrurcr09",
        email="nguyenphuc1234sonhoapy@gmail.com",
    )
    create_learner_account(session, me_account)

    collections_map = {}
    unique_collection_names = list(CEFR_MAPPING.values())
    for collection_name in unique_collection_names:
        collection = Collection(
            name=collection_name,
            creator=system_account.learner,
        )
        session.add(collection)
        session.flush()
        collections_map[collection_name] = collection

    brick_metadata_df = pd.read_csv("metadata.csv")

    brick_metadata_df["parsed_lesson_id"] = brick_metadata_df[
        "lesson_id"
    ].apply(lambda x: int(str(x).split("_")[1]) if not pd.isna(x) else None)

    # Map each lesson_id to exactly one collection based on the first occurrence's CEFR level
    lesson_collection_map = {}
    for _, row in brick_metadata_df.dropna(
        subset=["parsed_lesson_id"]
    ).iterrows():
        lesson_id = row["parsed_lesson_id"]
        if lesson_id not in lesson_collection_map:
            raw_cefr = row["cefr_level"]
            mapped_name = CEFR_MAPPING[raw_cefr]
            if mapped_name in collections_map:
                lesson_collection_map[lesson_id] = collections_map[mapped_name]

    for _, row in brick_metadata_df.iterrows():
        # Get the targeted human group string using your CEFR mapping system
        raw_cefr = row["cefr_level"]
        lesson_id = row["parsed_lesson_id"]
        target_collection = lesson_collection_map.get(lesson_id)

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
            cefr_level=raw_cefr,
            target_text_log_freq=text_utils.log_frequency(
                row["en_source_text"]
            ),
            creator=system_account.learner,
            brick_metadata=brick_metadata,
            collection_id=target_collection.id,
            lesson_id=lesson_id,
        )
        session.add(brick)

    # delete empty collections
    remaining_collections = []
    for collection in collections_map.values():
        has_brick = session.exec(
            select(Brick.id).where(Brick.collection_id == collection.id)
        ).first()

        if has_brick:
            remaining_collections.append(collection)
        else:
            session.delete(collection)

    print(
        f"{len(brick_metadata_df)} bricks imported across "
        f"{len(remaining_collections)} master categories!"
    )
    session.commit()


def init_snippets(session: Session):

    def import_common_voice(csv_name: str, creator_id: int = 1):
        df = pd.read_csv(csv_name)
        snippets = []

        for row in df.to_dict("records"):
            audio_path = f"{settings.snippets_folder}/{row['filename']}"
            snippets.append(
                Snippet(
                    content=row["text"],
                    audio_path=str(audio_path),
                    creator_id=creator_id,
                    log_frequency=text_utils.log_frequency(row["text"]),
                    audio_duration=float(row["duration"]),
                )
            )

        session.add_all(snippets)
        session.commit()

        print(f"{len(snippets)} snippets was imported from {csv_name}")

    import_common_voice("snippets-metadata.csv")


def transfer_knowledge_graph_data():
    engine_old = create_engine("sqlite:///knowledge_graph.db", echo=False)
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
            columns = session_old.exec(
                text(f"PRAGMA table_info({table_name})")
            ).all()
            col_names = [col[1] for col in columns]
            all_data[table_name] = [dict(zip(col_names, row)) for row in rows]

    with Session(engine) as session_new:
        try:
            for table_name, model in dict_mapping.items():
                valid_fields = model.model_fields.keys()
                for data in all_data[table_name]:
                    filtered = {
                        k: v for k, v in data.items() if k in valid_fields
                    }
                    session_new.add(model(**filtered))
            session_new.commit()
            print("Knowledge graph data transferred successfully.")
        except Exception as e:
            session_new.rollback()
            raise e


def transfer_subtitles():
    engine_old = create_engine("sqlite:///ytb_subtitles.db")

    with engine_old.connect() as conn_old:
        # We select the columns exactly as they are in SQLite
        query = text(
            "SELECT video_id, start, duration, text FROM subtitle_search"
        )
        results = conn_old.execute(query).fetchall()

    # insert into the new Postgres table
    with Session(engine) as session_new:
        try:
            for row in results:
                # Map SQLite 'text' -> Postgres 'transcript'
                new_entry = YouTubeSubtitle(
                    video_id=row.video_id,
                    start=row.start,
                    duration=row.duration,
                    transcript=row.text,
                )
                session_new.add(new_entry)

            session_new.commit()
            print(
                f"Successfully transferred {len(results)} YouTube subtitles to Postgres!"
            )
        except Exception as e:
            session_new.rollback()
            print(f"Error during transfer: {e}")
