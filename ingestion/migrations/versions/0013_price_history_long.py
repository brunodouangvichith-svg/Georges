"""ajoute price_history_long (historique 10 ans via yfinance, ad hoc)

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history_long",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )


def downgrade() -> None:
    op.drop_table("price_history_long")
