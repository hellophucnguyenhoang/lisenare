from sqlmodel import Session, select
from sqlalchemy.sql import func
from app.database import Brick
from app.config import settings
from pathlib import Path

def get_brick(session: Session, id: int):
    """
    Return a Brick or None.
    """
    return session.exec(select(Brick).where(Brick.id == id)).first()

def iter_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file

def get_random_brick(session: Session):
    return session.exec(
        select(Brick)
        .order_by(func.random())
        .limit(1)
    ).first()