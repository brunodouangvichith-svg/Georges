"""ajoute company_fundamentals, dividends (import quotidien yfinance, ad hoc)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_fundamentals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.Date(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("long_name", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("long_business_summary", sa.Text(), nullable=True),
        sa.Column("full_time_employees", sa.Integer(), nullable=True),
        sa.Column("market_cap", sa.BigInteger(), nullable=True),
        sa.Column("trailing_pe", sa.Numeric(), nullable=True),
        sa.Column("forward_pe", sa.Numeric(), nullable=True),
        sa.Column("dividend_yield", sa.Numeric(), nullable=True),
        sa.Column("beta", sa.Numeric(), nullable=True),
        sa.Column("fifty_two_week_high", sa.Numeric(), nullable=True),
        sa.Column("fifty_two_week_low", sa.Numeric(), nullable=True),
        sa.Column("raw_info", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "observed_at", name="uq_company_fundamentals_symbol_date"),
    )

    op.create_table(
        "dividends",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "ex_date", name="uq_dividend_symbol_ex_date"),
    )


def downgrade() -> None:
    op.drop_table("dividends")
    op.drop_table("company_fundamentals")
