"""drop mistakecache table

Revision ID: a1b2c3d4e5f6
Revises: d4e7f9a2c501
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d4e7f9a2c501"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("mistakecache")


def downgrade() -> None:
    op.create_table(
        "mistakecache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("normalized_answer", sa.String(), nullable=False),
        sa.Column("mistake_type", sa.String(), nullable=False),
        sa.Column("grammar_point", sa.String(), nullable=True),
        sa.Column("explanation", sa.String(), nullable=True),
        sa.Column("suggested_fix", sa.String(), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_id",
            "normalized_answer",
            name="uq_mistakecache_qid_answer",
        ),
    )
    op.create_index(
        op.f("ix_mistakecache_question_id"), "mistakecache", ["question_id"]
    )
