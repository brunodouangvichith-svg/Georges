"""retire currency_pairs, fx_prices_ohlcv, carry_rate_snapshots, cot_positioning (panier Carry Trade retire a la demande de l'utilisateur)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-15

La feature Carry Trade (ingestion/, engine/, api/routers/carry_trade.py, web)
a ete supprimee entierement du code (voir CLAUDE.md). La migration 0009 qui a
cree ces 4 tables n'est pas modifiee/supprimee (9 migrations plus recentes en
dependent comme ancetre de chaine) -- cette migration les retire explicitement
a la place, comme toute autre evolution de schema inversee.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("cot_positioning")
    op.drop_table("carry_rate_snapshots")
    op.drop_table("fx_prices_ohlcv")
    op.drop_table("currency_pairs")


def downgrade() -> None:
    op.create_table(
        "currency_pairs",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("funding_currency", sa.Text(), nullable=False),
        sa.Column("target_currency", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )

    op.create_table(
        "fx_prices_ohlcv",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False),
        sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False),
        sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["currency_pairs.symbol"]),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )

    op.create_table(
        "carry_rate_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("rate_pct", sa.Numeric(), nullable=False),
        sa.Column("observed_at", sa.Date(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("currency", "observed_at", name="uq_carry_rate_snapshot_currency_date"),
    )

    op.create_table(
        "cot_positioning",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("lev_money_long", sa.Integer(), nullable=False),
        sa.Column("lev_money_short", sa.Integer(), nullable=False),
        sa.Column("open_interest_all", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("currency", "report_date", name="uq_cot_positioning_currency_date"),
    )
