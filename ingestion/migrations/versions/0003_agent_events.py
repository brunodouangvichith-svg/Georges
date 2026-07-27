"""ajoute agent_events (Phase 3, alimentée par la Phase 7)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("context", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_events_created_at", "agent_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_events_created_at", table_name="agent_events")
    op.drop_table("agent_events")
