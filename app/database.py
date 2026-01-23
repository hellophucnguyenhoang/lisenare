import os
import pandas as pd
import numpy as np
from collections.abc import Iterator
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session
from datetime import datetime, timezone
from pydantic import EmailStr
from pathlib import Path
from .config import settings
from .schemas import LearnerAccountCreate, CEFRLevel
from . import security


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    email: EmailStr | None = Field(default=None, index=True, unique=True)
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
    target_audio_uri: str
    cefr_level: CEFRLevel
    is_public: bool = True
    last_edit_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    creator_id: int = Field(foreign_key="learner.id")
    creator: Learner = Relationship(back_populates="bricks")
    collections: list[Collection] = Relationship(back_populates="bricks", link_model=CollectionBrick)
    study_sessions: list["StudySession"] | None = Relationship(back_populates="brick")

class StudySession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_target_text: str | None = None
    user_target_audio_uri: str | None = None
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
    def create_learner_account(session: Session, learner_account_create: LearnerAccountCreate) -> Account:
        """
        This function is duplicated in the same function name
        in the accounts service to solve the circular import.
        """
        learner = Learner(full_name=learner_account_create.full_name)

        hashed_password = security.get_password_hash(learner_account_create.password)
        account = Account(
            username=learner_account_create.username,
            hashed_password=hashed_password,
            email=learner_account_create.email,
            learner=learner
        )

        session.add(account)
        session.commit()
        session.refresh(account)
        return account
    
    initial_learner_account_create = LearnerAccountCreate(
        full_name="Sam Nguyen", 
        username="qwer",
        password="1234"
    )
    initial_account = create_learner_account(session, initial_learner_account_create)

    a1_collection = Collection(name="A1 Sentences", creator=initial_account.learner)
    a2_collection = Collection(name="A2 Sentences", creator=initial_account.learner)
    b1_collection = Collection(name="B1 Sentences", creator=initial_account.learner)
    b2_collection = Collection(name="B2 Sentences", creator=initial_account.learner)
    c1_collection = Collection(name="C1 Sentences", creator=initial_account.learner)
    c2_collection = Collection(name="C2 Sentences", creator=initial_account.learner)

    session.add(a1_collection)
    session.add(a2_collection)
    session.add(b1_collection)
    session.add(b2_collection)
    session.add(c1_collection)
    session.add(c2_collection)

    level_to_collection = {
        CEFRLevel.A1: a1_collection,
        CEFRLevel.A2: a2_collection,
        CEFRLevel.B1: b1_collection,
        CEFRLevel.B2: b2_collection,
        CEFRLevel.C1: c1_collection,
        CEFRLevel.C2: c2_collection,
    }

    brick_metadata_df = pd.read_csv(os.path.join(settings.brick_folder, "metadata.csv"))
    for _, row in brick_metadata_df.iterrows():
        brick = Brick(
            native_text=row['vi_translation'], 
            target_text=row['en_source_text'],
            target_audio_uri=row['source_audio_path'],
            cefr_level=CEFRLevel(row['cefr_level']),
            collections=[],
            creator=initial_account.learner,
        )
        brick.collections.append(level_to_collection[brick.cefr_level])
        session.add(brick)
    session.commit()
