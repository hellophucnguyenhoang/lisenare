from sqlmodel import Session, select, func
from sqlalchemy.orm import selectinload
from app.database import Brick, BrickMetadata
import pandas as pd


def export_bricks_to_csv(
    session: Session, file_path: str = "bricks_export.csv"
):
    # 1. Fetch bricks with metadata joined
    statement = select(Brick).options(
        selectinload(Brick.brick_metadata).selectinload(
            BrickMetadata.grammar_points
        )
    )
    bricks = session.exec(statement).all()

    # 2. Flatten the data into a list of dictionaries
    data = []
    for b in bricks:
        br_mt = b.brick_metadata
        grammar_point_strings = [
            grm_p.grammar_point.value for grm_p in br_mt.grammar_points
        ]
        grammar_points_flatten = "|".join(grammar_point_strings)
        row = {
            "id": b.id,
            "native_text": b.native_text,
            "target_text": b.target_text,
            "cefr_level": b.cefr_level,
            "is_public": b.is_public,
            "collection_id": b.collection_id,
            # Metadata fields (flattened)
            "unit_type": br_mt.unit_type,
            "structure": br_mt.structure,
            "function": br_mt.function,
            "grammar_points": grammar_points_flatten,
        }
        data.append(row)

    # 3. Use Pandas to save to CSV
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    print(f"Exported {len(data)} bricks to {file_path}")
