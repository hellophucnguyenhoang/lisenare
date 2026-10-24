from sqlmodel import Session, select

from config import logger
from database import Brick


def export_bricks_to_csv(session: Session):
    stmt = select(Brick).where(Brick.embedding_id.is_(None))
    bricks = session.exec(stmt).all()
    logger.info("Result type: %s", type(bricks[0]))
