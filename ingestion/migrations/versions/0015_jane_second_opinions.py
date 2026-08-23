"""ajoute la table jane_second_opinions (persistance du second avis de Jane)

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jane_second_opinions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jane_second_opinions_decision_id", "jane_second_opinions", ["decision_id"])


def downgrade() -> None:
    op.drop_index("ix_jane_second_opinions_decision_id", table_name="jane_second_opinions")
    op.drop_table("jane_second_opinions")
