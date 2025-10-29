from sqlmodel import create_engine, SQLModel, Session, select
# from .models import User, Reading, ObjectiveQuestion, Topic, UserTopicLink, StudySession
from typing import Iterator



sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
