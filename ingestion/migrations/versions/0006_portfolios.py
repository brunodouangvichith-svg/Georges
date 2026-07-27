"""ajoute les portefeuilles nommés (web/, écran Mon Portefeuille)

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "portfolio_decisions",
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("decision_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decision_id"], ["decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("portfolio_id", "decision_id"),
    )


def downgrade() -> None:
    op.drop_table("portfolio_decisions")
    op.drop_table("portfolios")
