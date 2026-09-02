from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect
from sqlmodel import (
    Session,
    SQLModel,
    create_engine,
    text,
)

from app import security
from app.config import logger, settings
from app.schemas import (
    LearnerAccountCreate,
)

from .models import (
    Account,
    Brick,
    Collection,
    Learner,
    Snippet,
    Tag,
    Taggable,
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
        logger.info("Database tables not found, creating schema...")

        # Create SQLModel tables
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Enable Extensions
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            init_bricks(session)
            init_snippets(session)
            session.commit()

        transfer_subtitles()
        logger.info("Data initialization complete except embeddings.")
    else:
        logger.info("Database already initialized, skipping.")


def delete_db():
    # Drop the LangChain-managed tables (which SQLModel doesn't know about)
    with Session(engine) as session:
        session.exec(
            text("DROP TABLE IF EXISTS langchain_pg_embedding CASCADE;")
        )
        session.exec(
            text("DROP TABLE IF EXISTS langchain_pg_collection CASCADE;")
        )
        session.commit()

    # Drop SQLModel tables
    SQLModel.metadata.drop_all(engine)
    logger.info("Dropped all tables in the database.")


def init_bricks(session: Session):
    def create_learner_account(
        session: Session, learner_account_create: LearnerAccountCreate
    ) -> Account:
        # Create Learner first
        learner = Learner(name=learner_account_create.name)

        hashed_password = security.get_password_hash(
            learner_account_create.password
        )
        # Link via SQLModel relationship
        account = Account(
            username=learner_account_create.username,
            hashed_password=hashed_password,
            email=learner_account_create.email,
            learner=learner,
        )
        session.add(account)
        session.flush()  # Populates IDs without closing transaction
        return account

    # Create initial accounts
    system_account_create = LearnerAccountCreate()
    create_learner_account(session, system_account_create)

    me_account_create = LearnerAccountCreate(
        name="Phúc",
        username="hoangphuc",
        email="hellophucnh@gmail.com",
    )
    me_account = create_learner_account(session, me_account_create)

    odd_collection = Collection(
        name="Odd Collection",
        creator=me_account.learner,
    )
    odd_col_tags = [
        Tag(
            name="odd english",
            creator=me_account.learner,
        ),
        Tag(
            name="odd",
            creator=me_account.learner,
        ),
    ]

    even_collection = Collection(
        name="Even Collection",
        creator=me_account.learner,
    )
    even_col_tags = [
        Tag(
            name="even english",
            creator=me_account.learner,
        ),
        Tag(
            name="even",
            creator=me_account.learner,
        ),
    ]

    session.add_all([odd_collection, even_collection])

    for tag in odd_col_tags:
        session.add(tag)
    for tag in even_col_tags:
        session.add(tag)

    session.flush()

    for tag in odd_col_tags:
        session.add(
            Taggable(
                tag_id=tag.id,
                taggable_id=odd_collection.id,
                taggable_type="Collection",
            )
        )

    for tag in even_col_tags:
        session.add(
            Taggable(
                tag_id=tag.id,
                taggable_id=even_collection.id,
                taggable_type="Collection",
            )
        )

    session.flush()

    # Read and parse data with Pandas efficiently
    lesson_tags: dict[int, Tag] = {}
    brick_metadata_df = pd.read_csv("bricks-metadata.csv")

    brick_metadata_df["lesson_id"] = (
        brick_metadata_df["lesson_id"]
        .astype(str)
        .str.split("_")
        .str[1]
        .astype(int)
    )

    for _, row in brick_metadata_df.iterrows():
        lesson_id = int(row["lesson_id"])

        collection = odd_collection if lesson_id % 2 == 1 else even_collection

        brick = Brick(
            native_text=row["vi_translation"],
            target_text=row["en_source_text"],
            target_audio_path=str(
                Path("brick-audios") / row["source_audio_file"]
            ),
            unit_type=row["unit_type"],
            creator=me_account.learner,
            collection=collection,
        )

        session.add(brick)
        session.flush()  # obtain brick.id

        tag = lesson_tags.get(lesson_id)

        if tag is None:
            tag = Tag(
                name=f"Lesson {lesson_id}",
                creator=me_account.learner,
            )
            session.add(tag)
            session.flush()

            lesson_tags[lesson_id] = tag

        session.add(
            Taggable(
                tag_id=tag.id,
                taggable_id=brick.id,
                taggable_type="Brick",
            )
        )

    session.commit()

    logger.info(
        f"Imported {len(brick_metadata_df)} bricks, "
        f"{len(lesson_tags)} lesson tags."
    )


def init_snippets(session: Session):
    csv_name = "snippets-metadata.csv"
    creator_id: int = 1

    df = pd.read_csv(csv_name)
    snippets = []

    for row in df.to_dict("records"):
        audio_path = Path("snippets-audios") / row["filename"]
        snippets.append(
            Snippet(
                content=row["text"],
                content_audio_path=str(audio_path),
                creator_id=creator_id,
            )
        )

    session.add_all(snippets)
    session.commit()
    logger.info(f"{len(snippets)} snippets imported from {csv_name}")


def transfer_subtitles():
    engine_old = create_engine("sqlite:///ytb_subtitles.db")
    with engine_old.connect() as conn_old:
        query = text(
            "SELECT video_id, start, duration, text FROM subtitle_search"
        )
        results = conn_old.execute(query).fetchall()

    with Session(engine) as session_new:
        try:
            for row in results:
                new_entry = YouTubeSubtitle(
                    video_id=row.video_id,
                    start=row.start,
                    duration=row.duration,
                    transcript=row.text,
                )
                session_new.add(new_entry)

            session_new.commit()
            logger.info(
                f"Transferred {len(results)} YouTube subtitles to the database."
            )
        except Exception as e:
            session_new.rollback()
            logger.info(f"Error during transfer: {e}")
