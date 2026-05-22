"""add exercise type to exercise

Revision ID: f01325de0562
Revises: 3299979c250a
Create Date: 2026-05-19 22:40:13.512109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f01325de0562'
down_revision: Union[str, Sequence[str], None] = '3299979c250a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    exercise_type_enum = sa.Enum("REVIEW", "PRACTICE", name="exercisetype")
    exercise_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "exercise",
        sa.Column(
            "exercise_type",
            exercise_type_enum,
            nullable=False,
            server_default="PRACTICE",
        ),
    )
    op.alter_column("exercise", "exercise_type", server_default=None)


def downgrade() -> None:
    op.drop_column("exercise", "exercise_type")

    exercise_type_enum = sa.Enum("REVIEW", "PRACTICE", name="exercisetype")
    exercise_type_enum.drop(op.get_bind(), checkfirst=True)
