"""ajoute energy_price_snapshots (marché de l'énergie via OilPriceAPI, ad hoc)

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "energy_price_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("commodity_code", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("change_24h_pct", sa.Numeric(), nullable=True),
        sa.Column("price_observed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commodity_code", "snapshot_date", name="uq_energy_price_snapshot_commodity_date"),
    )


def downgrade() -> None:
    op.drop_table("energy_price_snapshots")
