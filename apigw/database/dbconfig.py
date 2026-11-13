from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import security
from config import logger, settings
from schemas import LearnerAccountCreate

from .models import (
    Account,
    Base,
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


def init_db(init_data: bool = False) -> None:
    """Initialize the database schema and seed data if necessary."""
    try:
        logger.info("Initializing database schema...")

        with Session(engine) as session:
            session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            session.execute(text("CREATE EXTENSION IF NOT EXISTS pgroonga;"))
            session.commit()

        logger.info("Database extensions enabled.")

        inspector = inspect(engine)

        if not inspector.has_table("brick"):
            Base.metadata.create_all(engine)
            logger.info("Database tables created.")

            if init_data:
                with Session(engine) as session:
                    init_bricks(session)

                logger.info(
                    "Database data initialized EXCEPT brick embeddings."
                )
            else:
                logger.info("Skipping data initialization.")
        else:
            logger.info("Database already initialized, skipping.")

    except Exception as e:
        logger.critical(
            f"Database connection or initialization failed: {e}",
            exc_info=True,
        )
        raise


def reset_dev_database() -> None:
    if not settings.is_production:
        with Session(engine) as session:
            session.execute(text("DROP SCHEMA public CASCADE;"))
            session.execute(text("CREATE SCHEMA public;"))
            session.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            session.commit()

        logger.info("Dropped and recreated a clean dev public schema.")


def create_learner_account(
    session: Session,
    learner_account_create: LearnerAccountCreate,
) -> Account:
    learner = Learner(
        name=learner_account_create.name,
        setting=LearnerSetting(),
    )

    account = Account(
        username=learner_account_create.username,
        hashed_password=security.get_password_hash(
            learner_account_create.password
        ),
        email=learner_account_create.email,
        learner=learner,
    )

    session.add(account)
    session.flush()

    return account


def init_bricks(session: Session) -> None:
    system_account_create = LearnerAccountCreate(
        name="The Avid Learner",
        username="hoangphuc",
        password="icandoit",
        email="hellophucnh@gmail.com",
    )

    me_account = create_learner_account(session, system_account_create)
    learner = me_account.learner

    islands = [
        Island(name=f"Island {i + 1}", creator=learner) for i in range(10)
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

    lesson_sizes = brick_metadata_df["lesson_id"].value_counts()

    for _, row in brick_metadata_df.iterrows():
        lesson_id = int(row["lesson_id"])

        if lesson_id not in lesson_islands:
            lesson_size = int(lesson_sizes[lesson_id])

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

        brick = Brick(
            native_text=row["vi_translation"],
            target_text=row["en_source_text"],
            target_audio_path=str(
                Path("system-brick-audios") / row["source_audio_file"]
            ),
            target_lang="en",
            kind=row["kind"],
            creator=learner,
            island=lesson_islands[lesson_id],
            is_private=False,
        )

        session.add(brick)
        session.flush()

        tag = lesson_tags.get(lesson_id)

        if tag is None:
            tag = Tag(
                name=f"lesson{lesson_id}",
                creator=learner,
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
