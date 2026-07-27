"""ajoute le cycle de vie des décisions et le rattachement au pattern (Phase 6)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("decisions", sa.Column("pattern_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_decisions_pattern_id", "decisions", "patterns_detected", ["pattern_id"], ["id"]
    )
    # `server_default` rétroactif uniquement pour ne pas casser les 3 lignes
    # illustratives déjà en base (voir ingestion/seed_demo.py) — elles étaient
    # déjà présentées comme définitives avant que ce cycle de statuts
    # n'existe. Le code applicatif fixe toujours `status` explicitement.
    op.add_column("decisions", sa.Column("status", sa.Text(), nullable=False, server_default="confirmee"))
    op.add_column("decisions", sa.Column("exit_scenario", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("exit_volume_confirmed", sa.Boolean(), nullable=True))
    op.add_column("decisions", sa.Column("exit_justification", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("exit_proposed_at", sa.TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "exit_proposed_at")
    op.drop_column("decisions", "exit_justification")
    op.drop_column("decisions", "exit_volume_confirmed")
    op.drop_column("decisions", "exit_scenario")
    op.drop_column("decisions", "status")
    op.drop_constraint("fk_decisions_pattern_id", "decisions", type_="foreignkey")
    op.drop_column("decisions", "pattern_id")
