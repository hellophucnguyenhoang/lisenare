from typing import Iterator
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session
from datetime import datetime, timezone
from pydantic import EmailStr
from pathlib import Path
import os
import pandas as pd
from .config import settings
import numpy as np

class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    email: EmailStr = Field(index=True, unique=True)
    last_login_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    learner_id: int = Field(foreign_key="learner.id", unique=True)
    learner: "Learner" = Relationship(back_populates="account")

class Learner(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    full_name: str
    collections: list["Collection"] | None = Relationship(back_populates="creator")
    bricks: list["Brick"] | None = Relationship(back_populates="creator")
    study_sessions: list["StudySession"] | None = Relationship(back_populates="learner")
    account: Account | None = Relationship(back_populates="learner") # Allow null in runtime

class CollectionBrick(SQLModel, table=True):
    collection_id: int | None = Field(default=None, foreign_key="collection.id", primary_key=True)
    brick_id: int | None = Field(default=None, foreign_key="brick.id", primary_key=True)

class Collection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="collections")
    bricks: list["Brick"] | None = Relationship(back_populates="collections", link_model=CollectionBrick)

class Brick(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    native_text: str
    target_text: str
    target_audio_url: str
    is_public: bool = True
    last_edit_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="bricks")
    collections: list[Collection] = Relationship(back_populates="bricks", link_model=CollectionBrick)
    study_sessions: list["StudySession"] | None = Relationship(back_populates="brick")

class StudySession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_target_text: str | None = None
    user_target_audio_url: str | None = None
    enrolled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float | None = None
    learner_id: int = Field(foreign_key="learner.id")
    brick_id: int = Field(foreign_key="brick.id")
    learner: Learner = Relationship(back_populates="study_sessions")
    brick: Brick = Relationship(back_populates="study_sessions")

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
        print("Done creating tables.")
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
    admin_learner = Learner(full_name="Sam Nguyen")
    session.add(admin_learner)
    session.commit()
    session.refresh(admin_learner)
    collection1 = Collection(name="First Essential 1500 Words", creator=admin_learner)
    collection2 = Collection(name="Second Essential 1500 Words", creator=admin_learner)
    session.add(collection1)
    brick_metadata_df = pd.read_csv(os.path.join(settings.brick_folder, "metadata.csv"))
    for _, row in brick_metadata_df.iterrows():
        brick = Brick(
            native_text=row['vi_translation'], 
            target_text=row['en_source_text'],
            target_audio_url=row['source_audio_path'],
            collections=[],
            creator=admin_learner,
        )
        if np.random.random() > 0.5:
            brick.collections.append(collection1)
        else:
            brick.collections.append(collection2)
        session.add(brick)
    session.commit()
