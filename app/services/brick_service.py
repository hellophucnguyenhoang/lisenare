from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, or_, select

from app.config import settings
from app.database import (
    Brick,
    BrickMetadata,
    BrickMetadataGrammarPoint,
    BrickOverride,
    Collection,
    LearningCard,
)
from app.schemas import BrickCreate, BrickCreateRequest, BrickUpdate, UnitType

from . import collection_service


def get_pending_bricks_subquery(learner_id: int):
    """
    A brick is considered pending of a learner if it's created or has a
    override version created by that learner.
    """
    return (
        select(Brick)
        .join(BrickOverride, isouter=True)
        .where(
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            )
        )
        .subquery()
    )


def get_pending_bricks(
    session: Session,
    learner_id: int,
    collection_id: int | None = None,
    group_names: list[str] | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> list[Brick]:
    """
    A brick is considered pending of a learner if it's created or has a
    override version created by that learner.
    """
    statement = select(Brick).join(BrickOverride, isouter=True)

    conditions = []
    if collection_id:
        conditions.append(Brick.collection_id == collection_id)

    conditions.append(
        or_(
            Brick.creator_id == learner_id,
            BrickOverride.learner_id == learner_id,
        )
    )

    if group_names:
        statement = statement.join(Collection, isouter=True)
        conditions.append(Collection.group_name.in_(group_names))

    statement = statement.where(*conditions).order_by(Brick.id)

    if limit is not None:
        statement = statement.limit(limit)

    if offset is not None:
        statement = statement.offset(offset)

    return session.exec(statement).all()


def get_brick(session: Session, id: int, learner_id: int) -> Brick:
    statement = (
        select(Brick)
        # eager loading the nested metadata and its grammar points
        .options(
            selectinload(Brick.brick_metadata).selectinload(
                BrickMetadata.grammar_points
            )
        )
        .join(
            BrickOverride, isouter=True
        )  # Use outer join in case override doesn't exist
        .where(
            Brick.id == id,
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            ),
        )
    )

    result = session.exec(statement).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Brick not found"
        )

    brick = result

    # filter the specific override for the learner and apply if it exists
    if brick.overrides:
        specific_override = next(
            (o for o in brick.overrides if o.learner_id == learner_id), None
        )
        if specific_override:
            brick.native_text = specific_override.native_text

    return brick


def iter_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        yield from audio_file


async def get_audio_file(filename: str):
    base_dir = Path(settings.brick_folder)
    file_path = (base_dir / filename).resolve()
    with open(file_path, "rb") as audio_file:
        return audio_file.read()


def get_broken_filenames() -> set[str]:
    REPORT_FILE = Path(settings.broken_report_file)
    if not REPORT_FILE.exists():
        return set()
    # Read and split by "|", taking the first part (filename)
    with REPORT_FILE.open("r") as f:
        return {
            f"brick-audios/{line.split('|')[0]}" for line in f if "|" in line
        }


def get_brick_fsrs(
    session: Session,
    learner_id: int,
    collection_ids: list[int] | None = None,
) -> Brick | None:
    now = datetime.now(timezone.utc)
    broken_files = get_broken_filenames()

    def apply_filters(stmt):
        if collection_ids:
            stmt = stmt.where(Brick.collection_id.in_(collection_ids))
        if broken_files:
            stmt = stmt.where(~Brick.target_audio_uri.in_(broken_files))
        return stmt

    def resolve_override(result):
        if not result:
            return None
        brick, override_native = result
        if override_native:
            brick.native_text = override_native
        return brick

    # Common override join condition
    override_join = (BrickOverride.brick_id == Brick.id) & (
        BrickOverride.learner_id == learner_id
    )

    # 1. Due cards
    due_stmt = (
        select(Brick, BrickOverride.native_text)
        .join(LearningCard, LearningCard.brick_id == Brick.id)
        .join(BrickMetadata)
        .outerjoin(BrickOverride, override_join)
        .where(
            LearningCard.learner_id == learner_id,
            LearningCard.due <= now,
            BrickMetadata.unit_type == UnitType.sentence,
        )
        .order_by(LearningCard.due)
        .limit(1)
    )

    due_stmt = apply_filters(due_stmt)
    result = session.exec(due_stmt).first()
    brick = resolve_override(result)
    if brick:
        return brick

    # 2. New unseen bricks
    pending_bricks_subq = get_pending_bricks_subquery(learner_id)

    new_stmt = (
        select(Brick, BrickOverride.native_text)
        .join(pending_bricks_subq, pending_bricks_subq.c.id == Brick.id)
        .join(BrickMetadata)
        .outerjoin(BrickOverride, override_join)
        .where(
            BrickMetadata.unit_type == UnitType.sentence,
            ~Brick.id.in_(
                select(LearningCard.brick_id).where(
                    LearningCard.learner_id == learner_id
                )
            ),
        )
        .order_by(func.length(Brick.target_text))
        .limit(1)
    )

    new_stmt = apply_filters(new_stmt)
    result = session.exec(new_stmt).first()
    return resolve_override(result)


def get_brick_in_collection_learn(
    session: Session,
    learner_id: int,
    collection_id: int,
    brick_order: int = 1,
) -> dict | None:
    stmt = (
        select(Brick, BrickOverride.native_text)
        .distinct()
        .join(BrickOverride, full=True)
        .where(
            Brick.collection_id == collection_id,
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            ),
        )
        .order_by(func.length(Brick.target_text))
    )
    bricks_overrides = session.exec(stmt).all()
    if not bricks_overrides:
        return None

    brick, override_native = bricks_overrides[brick_order - 1]
    if override_native:
        brick.native_text = override_native

    total_bricks = len(bricks_overrides)
    return {
        "brick": brick,
        "total_bricks": total_bricks,
    }


def update_brick(
    session: Session,
    brick_id: int,
    brick_update: BrickUpdate,
    learner_id: int,
) -> Brick:

    statement = (
        select(Brick)
        .where(Brick.id == brick_id)
        .options(
            selectinload(Brick.brick_metadata).selectinload(
                BrickMetadata.grammar_points
            )
        )
    )
    brick = session.exec(statement).first()
    if not brick:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brick not found",
        )

    update_data = brick_update.model_dump(
        exclude_unset=True,
    )

    # Case 1: Author edits original
    if brick.creator_id == learner_id:
        # Handle nested metadata separately
        if "brick_metadata" in update_data:
            metadata_data = update_data.pop("brick_metadata")

            # Handle grammar points first
            grammar_points_data = metadata_data.pop("grammar_points", None)
            if grammar_points_data is not None:
                brick.brick_metadata.grammar_points = []
                for gp in grammar_points_data:
                    # Access dictionary key safely
                    new_gp = BrickMetadataGrammarPoint(
                        brick_metadata_id=brick.brick_metadata_id,
                        grammar_point=gp["grammar_point"],
                    )
                    brick.brick_metadata.grammar_points.append(new_gp)

            # Update other metadata fields (unit_type, structure, function)
            for key, value in metadata_data.items():
                setattr(brick.brick_metadata, key, value)

        # Update top-level brick fields
        for key, value in update_data.items():
            setattr(brick, key, value)

        brick.last_edit_at = datetime.now(timezone.utc)
        session.add(brick)
        session.commit()
        session.refresh(brick)
        return brick

    # --- Case 2: Non-author edits ---
    else:
        # Check for forbidden fields
        forbidden_fields = {
            "target_text",
            "brick_metadata",
            "is_public",
            "collection_id",
        }
        attempted_forbidden = forbidden_fields.intersection(update_data.keys())
        if attempted_forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Only the author can edit: {', '.join(attempted_forbidden)}. "
                f"Change the English text to create your own version.",
            )

        # Proceed with native_text override
        override = session.get(BrickOverride, (learner_id, brick_id))
        if not override:
            override = BrickOverride(learner_id=learner_id, brick_id=brick_id)

        if "native_text" in update_data:
            override.native_text = update_data["native_text"]

        override.last_edit_at = datetime.now(timezone.utc)
        session.add(override)
        session.commit()
        session.refresh(override)

        # Return the brick with the user's specific translation
        brick.native_text = override.native_text
        return brick


def create_brick(
    session: Session,
    request_data: BrickCreateRequest,
    creator_id: int,
    file_path: str,
) -> Brick:
    metadata_data = request_data.brick_metadata.model_dump(
        exclude={"grammar_points"}
    )
    brick_metadata = BrickMetadata(**metadata_data)

    grammar_points_data = request_data.brick_metadata.grammar_points or []
    grammar_points = [
        BrickMetadataGrammarPoint(grammar_point=gp.grammar_point)
        for gp in grammar_points_data
    ]
    brick_metadata.grammar_points = grammar_points

    brick_create = BrickCreate(
        native_text=request_data.native_text,
        target_text=request_data.target_text,
        target_audio_uri=file_path,  # e.g. "brick-audios/learner_1_audio.m4a"
        is_public=request_data.is_public,
        creator_id=creator_id,
        collection_name=request_data.collection_name,
        group_name=request_data.group_name,
    )
    brick = Brick.model_validate(brick_create)
    brick.brick_metadata = brick_metadata
    session.add(brick)

    collection = collection_service.get_or_create_collection(
        session,
        brick_create.collection_name,
        brick_create.group_name,
        brick_create.creator_id,
    )

    collection.bricks.append(brick)

    session.commit()
    session.refresh(brick)

    collection_service.update_collection_difficulty(session, collection.id)

    return brick
