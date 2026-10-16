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
    # Use SQLAlchemy to check if tables exist
    inspector = inspect(engine)
    if not inspector.has_table("brick"):
        logger.info("Database tables not found, creating schema...")

        # Create SQLModel tables
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            # Enable Extensions
            session.exec(text("CREATE EXTENSION IF NOT EXISTS vector;"))

            init_bricks(session)
            session.commit()

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
    system_account_create = LearnerAccountCreate()
    create_learner_account(session, system_account_create)

    me_account_create = LearnerAccountCreate(
        name="Phúc",
        username="hoangphuc",
        email="hellophucnh@gmail.com",
    )
    me_account = create_learner_account(session, me_account_create)

    odd_island = Island(
        name="Odd Island",
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

    even_island = Island(
        name="Even Island",
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

    session.add_all([odd_island, even_island])

    for tag in odd_col_tags:
        session.add(tag)
    for tag in even_col_tags:
        session.add(tag)

    session.flush()

    for tag in odd_col_tags:
        session.add(
            Taggable(
                tag_id=tag.id,
                taggable_id=odd_island.id,
                taggable_type="Island",
            )
        )

    for tag in even_col_tags:
        session.add(
            Taggable(
                tag_id=tag.id,
                taggable_id=even_island.id,
                taggable_type="Island",
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

        island = odd_island if lesson_id % 2 == 1 else even_island

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
