"""ajoute strategic_reports, virtual_portfolio_trades, virtual_portfolio_snapshots (rapport strategique hebdomadaire + portefeuille virtuel)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategic_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("narrative_markdown", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategic_reports_created_at", "strategic_reports", ["created_at"])
    op.create_table(
        "virtual_portfolio_trades",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("side", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("fees", sa.Numeric(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("executed_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["strategic_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.CheckConstraint("side IN ('achat', 'vente')", name="ck_virtual_portfolio_trade_side"),
        sa.CheckConstraint("quantity > 0", name="ck_virtual_portfolio_trade_quantity"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "virtual_portfolio_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("valued_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("cash", sa.Numeric(), nullable=False),
        sa.Column("positions_value", sa.Numeric(), nullable=False),
        sa.Column("total_value", sa.Numeric(), nullable=False),
        sa.Column("fees_total", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["strategic_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", name="uq_virtual_portfolio_snapshot_report"),
    )


def downgrade() -> None:
    op.drop_table("virtual_portfolio_snapshots")
    op.drop_table("virtual_portfolio_trades")
    op.drop_index("ix_strategic_reports_created_at", table_name="strategic_reports")
    op.drop_table("strategic_reports")
