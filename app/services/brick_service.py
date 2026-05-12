from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, and_, delete, desc, func, or_, select

from app.database import (
    Brick,
    BrickMetadata,
    BrickMetadataGrammarPoint,
    BrickOverride,
    Collection,
    LearningCard,
    Review,
)
from app.schemas import BrickCreate, BrickCreateRequest, BrickUpdate, UnitType

from . import collection_service
from . import context_search_service as search_service


def get_pending_bricks_subquery(learner_id: int):
    """
    A brick is considered pending of a learner if it's created or has an
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

    # A Brick can have 0 to many BrickOverride
    # A creator cannot have an override for a Brick he created
    # Left join to get all bricks, and its possible overrides from learner_id
    statement = select(
        Brick,
        func.coalesce(BrickOverride.native_text, Brick.native_text).label(
            "final_native_text"
        ),
        func.coalesce(
            BrickOverride.target_audio_path, Brick.target_audio_path
        ).label("final_target_audio_path"),
    ).join(
        BrickOverride,
        and_(
            BrickOverride.brick_id == Brick.id,
            BrickOverride.learner_id == learner_id,
        ),
        isouter=True,
    )

    conditions = []

    # The conditions of a brick to be called a pending brick
    conditions.append(
        or_(
            Brick.creator_id == learner_id,
            BrickOverride.learner_id == learner_id,
        )
    )

    if collection_id:
        conditions.append(Brick.collection_id == collection_id)

    if group_names:
        statement = statement.join(Collection, isouter=True)
        conditions.append(Collection.group_name.in_(group_names))

    statement = statement.where(*conditions).order_by(Brick.id)

    if limit is not None:
        statement = statement.limit(limit)

    if offset is not None:
        statement = statement.offset(offset)

    results = session.exec(statement).all()

    bricks = []
    for brick, final_native_text, final_target_audio_path in results:
        # the final_native_text is either from the original brick or
        # its overridden depends on whether the learner is the creator
        # or not, and cannot be null because Brick.native_text can't
        brick.native_text = final_native_text
        brick.target_audio_path = final_target_audio_path
        bricks.append(brick)

    return bricks


def count_pending_bricks(
    session: Session,
    learner_id: int,
    collection_id: int | None = None,
    group_names: list[str] | None = None,
) -> int:
    statement = (
        select(func.count(Brick.id))
        .select_from(Brick)
        .join(BrickOverride, isouter=True)
    )

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

    statement = statement.where(*conditions)
    return session.exec(statement).one()


def get_brick(
    session: Session, id: int, learner_id: int | None = None
) -> Brick:
    # 1. Build the base filters
    # Everyone can see public bricks
    filters = [Brick.is_public]

    # If logged in, also allow if they are the creator or have an override
    if learner_id:
        filters.append(Brick.creator_id == learner_id)
        filters.append(BrickOverride.learner_id == learner_id)

    statement = (
        select(Brick)
        .options(
            selectinload(Brick.brick_metadata).selectinload(
                BrickMetadata.grammar_points
            ),
            selectinload(Brick.creator),
        )
        .join(BrickOverride, isouter=True)
        .where(
            Brick.id == id,
            or_(*filters),  # Unpacks the list into the OR condition
        )
    )

    result = session.exec(statement).first()

    if not result:
        # Note: Using 404 for private bricks keeps the DB structure more secure
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Brick not found"
        )

    brick = result

    # 2. Only attempt to apply overrides if a learner_id exists
    if learner_id and brick.overrides:
        specific_override = next(
            (o for o in brick.overrides if o.learner_id == learner_id), None
        )
        if specific_override:
            brick.native_text = specific_override.native_text
            brick.target_audio_path = (
                specific_override.target_audio_path or brick.target_audio_path
            )

    return brick


def get_brick_fsrs(
    session: Session,
    learner_id: int,
    collection_ids: list[int] | None = None,
) -> Brick | None:
    now = datetime.now(timezone.utc)
    broken_files = set()  # get_broken_filenames()

    def apply_filters(stmt):
        if collection_ids:
            stmt = stmt.where(Brick.collection_id.in_(collection_ids))
        if broken_files:
            stmt = stmt.where(~Brick.target_audio_path.in_(broken_files))
        return stmt

    def resolve_override(result):
        if not result:
            return None

        brick, override_native_text, target_audio_path = result

        if override_native_text:
            brick.native_text = override_native_text

        if target_audio_path:
            brick.target_audio_path = target_audio_path

        return brick

    # Common override join condition
    # Only get the overrides of the learner_id
    override_join = (BrickOverride.brick_id == Brick.id) & (
        BrickOverride.learner_id == learner_id
    )

    # Case 1: Get the most overdue card
    due_stmt = (
        select(
            Brick, BrickOverride.native_text, BrickOverride.target_audio_path
        )
        .join(LearningCard, LearningCard.brick_id == Brick.id)
        .join(BrickMetadata)
        .join(BrickOverride, override_join, isouter=True)
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

    print("FSRS Case 2: Get new unseen card")
    # Case 2: Get new unseen card
    pending_bricks_subq = get_pending_bricks_subquery(learner_id)

    new_stmt = (
        select(
            Brick, BrickOverride.native_text, BrickOverride.target_audio_path
        )
        .join(pending_bricks_subq, pending_bricks_subq.c.id == Brick.id)
        .join(BrickMetadata)
        .join(BrickOverride, override_join, isouter=True)
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
        select(
            Brick,
            BrickOverride.native_text,
            BrickOverride.target_audio_path,
            func.length(Brick.target_text).label("target_text_len"),
        )
        .distinct()
        .join(BrickOverride, isouter=True)
        .where(
            Brick.collection_id == collection_id,
            or_(
                Brick.creator_id == learner_id,
                BrickOverride.learner_id == learner_id,
            ),
        )
        .order_by("target_text_len")
    )
    bricks_overrides = session.exec(stmt).all()
    if not bricks_overrides:
        return None

    brick, override_native_text, target_audio_path, _ = bricks_overrides[
        brick_order - 1
    ]
    if override_native_text:
        brick.native_text = override_native_text

    if target_audio_path:
        brick.target_audio_path = target_audio_path

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
    target_audio_path: str | None = None,
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

        # Update audio if a new file was uploaded
        if target_audio_path:
            brick.target_audio_path = target_audio_path

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

        # Update override audio if provided
        if target_audio_path:
            override.target_audio_path = target_audio_path

        override.last_edit_at = datetime.now(timezone.utc)
        session.add(override)
        session.commit()
        session.refresh(override)

        # Return the brick with the user's specific translation
        brick.native_text = override.native_text

        # Ensure the response shows the override audio, not the author's
        if override.target_audio_path:
            brick.target_audio_path = override.target_audio_path

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
        target_audio_path=file_path,  # e.g. "brick-audios/learner_1_audio.m4a"
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

    collection_service.update_collection_difficulty(
        session, collection.id, creator_id
    )

    search_service.add_item_to_vector_store(
        search_service=search_service.context_search_service,
        item=brick,
        store_key="bricks",
        text_getter=lambda b: f"{b.target_text} {b.native_text}",
        metadata_getter=lambda b: {
            "brick_id": b.id,
            "target_text": b.target_text,
            "native_text": b.native_text,
        },
        id_prefix="Brick",
    )
    return brick


def check_target_text_exists(session: Session, target_text: str) -> bool:
    # Use select to find a matching record
    statement = select(Brick).where(Brick.target_text == target_text)
    result = session.exec(statement).first()

    return result is not None


def get_transfer_owner_id(
    session: Session, brick_id: int, exclude_learner_id: int
) -> int | None:
    # 1. Aggregates for Reviews
    review_count = func.count(Review.id).label("review_count")
    last_review_at = func.max(Review.reviewed_at).label("last_review_at")

    # 2. Latest edit time from Overrides
    last_edit_at = func.max(BrickOverride.last_edit_at).label("last_edit_at")

    stmt = (
        # We select from BrickOverride because a learner must have an
        # override/card to be considered an "active user" of the brick
        select(BrickOverride.learner_id)
        .join(
            Review,
            (Review.brick_id == BrickOverride.brick_id)
            & (Review.learner_id == BrickOverride.learner_id),
            isouter=True,
        )
        .where(
            BrickOverride.brick_id == brick_id,
            BrickOverride.learner_id != exclude_learner_id,
        )
        .group_by(BrickOverride.learner_id)
        .order_by(
            desc(review_count),  # Priority 1: Most reviews
            desc(last_review_at),  # Priority 2: Most recent review
            desc(
                last_edit_at
            ),  # Priority 3: Most recent edit (for those without reviews)
            BrickOverride.learner_id.asc(),
        )
    )

    result = session.exec(stmt).first()
    return result  # Returns learner_id or None


def delete_brick(session: Session, learner_id: int, brick_id: int):
    brick = session.get(Brick, brick_id)
    if not brick:
        raise HTTPException(status_code=404, detail="Brick not found")
    collection_id = brick.collection_id
    status_msg = ""

    # Case 1: Creator deletes the actual Brick
    if brick.creator_id == learner_id:
        new_owner_id = get_transfer_owner_id(
            session, brick_id, exclude_learner_id=learner_id
        )

        # If someone else can own it, transfer ownership instead of deleting the brick
        if new_owner_id is not None:
            # Change the old brick's data to the new owner's data

            brick.creator_id = new_owner_id

            override = session.get(BrickOverride, (new_owner_id, brick_id))

            if override.native_text:
                brick.native_text = override.native_text

            if override.target_audio_path:
                brick.target_audio_path = override.target_audio_path

            brick.collection_id = override.collection_id

            # New user does not need his old override anymore
            session.delete(override)

            # Delete the interaction history of the old owner
            session.exec(
                delete(Review).where(
                    Review.learner_id == learner_id,
                    Review.brick_id == brick_id,
                )
            )

            card = session.get(LearningCard, (learner_id, brick_id))
            if card:
                session.delete(card)

            # Save the changes
            brick.last_edit_at = datetime.now(timezone.utc)
            session.commit()

            # Clean the collection of the old owner
            # because he has just deleted a brick
            collection_service.delete_empty_collection(session, collection_id)
            return "OWNERSHIP_TRANSFERRED"

        # No eligible new owner -> real delete is allowed
        try:
            session.delete(brick)
            session.commit()
            status_msg = "BRICK_DELETED"

            collection_service.delete_empty_collection(session, collection_id)
            search_service.delete_item_from_vector_store(
                search_service=search_service.context_search_service,
                item_id=brick_id,
                store_key="bricks",
                id_prefix="Brick",
            )
            return status_msg

        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete this brick because other learners are using it.",
            )

    # Case 2: Non-creator deletes personal/override data only
    # Check/Delete Override, Reviews, and LearningCard
    override = session.get(BrickOverride, (learner_id, brick_id))
    override_collection_id = override.collection_id
    session.delete(override)

    session.exec(
        delete(Review).where(
            Review.learner_id == learner_id,
            Review.brick_id == brick_id,
        )
    )

    card = session.get(LearningCard, (learner_id, brick_id))
    if card:
        session.delete(card)

    session.commit()
    status_msg = "PERSONAL_DATA_DELETED"
    collection_service.delete_empty_collection(session, override_collection_id)
    return status_msg
