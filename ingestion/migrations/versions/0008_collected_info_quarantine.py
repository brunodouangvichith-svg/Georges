"""ajoute collected_info_quarantine (Phase 7 MVP, module de validation)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collected_info_quarantine",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["securities.symbol"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collected_info_quarantine_created_at", "collected_info_quarantine", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_collected_info_quarantine_created_at", table_name="collected_info_quarantine")
    op.drop_table("collected_info_quarantine")
