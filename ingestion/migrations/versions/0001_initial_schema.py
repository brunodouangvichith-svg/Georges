"""schema initial : securities, prices_ohlcv (hypertable), patterns_detected, decisions, decision_outcomes

Revision ID: 0001
Revises:
Create Date: 2026-07-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "securities",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=False),
        sa.Column("theme", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("symbol"),
    )

    op.create_table(
        "prices_ohlcv",
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
    # `ts` est la colonne de partitionnement temporel de TimescaleDB.
    op.execute("SELECT create_hypertable('prices_ohlcv', 'ts')")

    op.create_table(
        "patterns_detected",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("pattern_type", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("context", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patterns_detected_symbol", "patterns_detected", ["symbol"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("decision_type", sa.Text(), nullable=False),
        sa.Column("entry_price", sa.Numeric(), nullable=False),
        sa.Column("take_profit", sa.Numeric(), nullable=True),
        sa.Column("stop_loss", sa.Numeric(), nullable=True),
        sa.Column("confidence", sa.Numeric(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_symbol", "decisions", ["symbol"])

    op.create_table(
        "decision_outcomes",
        sa.Column("decision_id", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("pnl_pct", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"]),
        sa.PrimaryKeyConstraint("decision_id", "evaluated_at"),
    )


def downgrade() -> None:
    op.drop_table("decision_outcomes")
    op.drop_index("ix_decisions_symbol", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_patterns_detected_symbol", table_name="patterns_detected")
    op.drop_table("patterns_detected")
    op.drop_table("prices_ohlcv")
    op.drop_table("securities")
