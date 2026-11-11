from sqlalchemy import select
from sqlalchemy.orm import Session

from config import logger
from database import Brick


def export_bricks_to_csv(session: Session):
    stmt = select(Brick).where(Brick.embedding_id.is_(None))
    bricks = session.scalars(stmt).all()
    logger.info("Result type: %s", type(bricks[0]))
