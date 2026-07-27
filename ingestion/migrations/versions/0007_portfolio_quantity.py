"""ajoute la quantité par ligne de portefeuille (répartition de budget)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolio_decisions", sa.Column("quantity", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("portfolio_decisions", "quantity")
