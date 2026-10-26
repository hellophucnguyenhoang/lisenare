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

import security
from config import logger, settings
from schemas import (
    LearnerAccountCreate,
)

from .models import (
    Account,
    Brick,
    Island,
    Learner,
    LearnerSetting,
    Tag,
    Taggable,
)

engine = create_engine(settings.db_url, echo=False)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def init_db():
    """
    Create the tables an insert data to them if the database does not exits.
    """
    try:
        logger.info("Initializing database schema...")

        # Enable extensions first
        with Session(engine) as session:
            # For LangChain semantic search
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            # For Japanese literal search
            session.exec(text("CREATE EXTENSION IF NOT EXISTS pgroonga;"))

            # Make extensions available globally right now
            session.commit()
            logger.info("Database extensions enabled.")

        # Use SQLAlchemy to check if tables exist
        inspector = inspect(engine)
        if not inspector.has_table("brick"):
            # Create SQLModel tables
            logger.info("Creating SQLModel tables...")
            SQLModel.metadata.create_all(engine)

            # Seed data
            with Session(engine) as session:
                init_bricks(session)
                session.commit()

            logger.info(
                "Data initialization complete EXCEPT brick embeddings."
            )
        else:
            logger.info("Database already initialized, skipping.")
    except Exception as e:
        logger.critical(
            f"Database connection or initialization failed: {e}",
            exc_info=True,
        )
        raise


def delete_db():
    with Session(engine) as session:
        # Keep legacy LangChain tables cleanup for environments that may still have them
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


def delete_db_force():
    with Session(engine) as session:
        # Drop the entire public schema and all its contents
        session.exec(text("DROP SCHEMA public CASCADE;"))

        # Recreate the blank public schema
        session.exec(text("CREATE SCHEMA public;"))

        # Grant default permissions back
        session.exec(text("GRANT ALL ON SCHEMA public TO public;"))
        session.commit()

    logger.info("Dropped and recreated a clean public schema.")


def init_bricks(session: Session):
    def create_learner_account(
        session: Session, learner_account_create: LearnerAccountCreate
    ) -> Account:
        # Create Learner first
        default_setting = LearnerSetting()
        learner = Learner(
            name=learner_account_create.name,
            setting=default_setting,
        )

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
    system_account_create = LearnerAccountCreate(
        name="The Avid Learner",
        username="qwerwert",
        password="12345678",
    )
    create_learner_account(session, system_account_create)

    me_account_create = LearnerAccountCreate(
        name="Phúc",
        username="hoangphuc",
        password="12345678",
        email="hellophucnh@gmail.com",
    )
    me_account = create_learner_account(session, me_account_create)

    islands = [
        Island(name=f"Island {i + 1}", creator=me_account.learner)
        for i in range(10)
    ]
    session.add_all(islands)
    session.flush()

    island_brick_counts = [0] * len(islands)
    lesson_islands: dict[int, Island] = {}
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

        if lesson_id not in lesson_islands:
            lesson_size = (brick_metadata_df["lesson_id"] == lesson_id).sum()

            # Find the first island with enough remaining capacity.
            island_index = next(
                (
                    i
                    for i, count in enumerate(island_brick_counts)
                    if count + lesson_size <= 1111
                ),
                None,
            )

            if island_index is None:
                raise ValueError(
                    f"Cannot assign lesson {lesson_id}: "
                    "no island has enough capacity."
                )

            lesson_islands[lesson_id] = islands[island_index]
            island_brick_counts[island_index] += lesson_size

        island = lesson_islands[lesson_id]

        brick = Brick(
            native_text=row["vi_translation"],
            target_text=row["en_source_text"],
            target_audio_path=str(
                Path("system-brick-audios") / row["source_audio_file"]
            ),
            target_lang="en",
            kind=row["kind"],
            creator=me_account.learner,
            island=island,
            is_private=False,
        )

        session.add(brick)
        session.flush()  # obtain brick.id

        tag = lesson_tags.get(lesson_id)
        if tag is None:
            tag = Tag(
                name=f"lesson{lesson_id}",
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
