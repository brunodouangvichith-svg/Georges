"""ajoute baskets, basket_securities, pattern_candidates (Phase 2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "baskets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "basket_securities",
        sa.Column("basket_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["basket_id"], ["baskets.id"]),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("basket_id", "symbol"),
    )
    op.create_index("ix_basket_securities_symbol", "basket_securities", ["symbol"])

    op.create_table(
        "pattern_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("pattern_type", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("context", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pattern_candidates_symbol", "pattern_candidates", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_pattern_candidates_symbol", table_name="pattern_candidates")
    op.drop_table("pattern_candidates")
    op.drop_index("ix_basket_securities_symbol", table_name="basket_securities")
    op.drop_table("basket_securities")
    op.drop_table("baskets")
