"""ajoute les tables Obligataire Watch (rendements obligataires, alertes, journal de collecte)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bond_yield_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column("value_pct", sa.Numeric(), nullable=False),
        sa.Column("observed_at", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument", "observed_at", name="uq_bond_yield_snapshot_instrument_date"),
    )
    # Pas d'index séparé sur `instrument` seul : l'index de
    # `uq_bond_yield_snapshot_instrument_date` ci-dessus sert déjà tout
    # filtre sur `instrument` (préfixe gauche), ce qui couvre
    # `load_latest_snapshot`/`load_history` (engine/compute_bond_yields.py) —
    # un second index sur la même colonne de tête ne ferait qu'ajouter du
    # coût d'écriture sans bénéfice de lecture (trouvé par /code-review).
    op.create_index("ix_bond_yield_snapshots_observed_at", "bond_yield_snapshots", ["observed_at"])

    op.create_table(
        "bond_alert_thresholds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("threshold_pct", sa.Numeric(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument", "direction", name="uq_bond_alert_threshold_instrument_direction"),
    )

    op.create_table(
        "bond_alert_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument", sa.Text(), nullable=False),
        sa.Column("threshold_id", sa.Integer(), nullable=False),
        sa.Column("threshold_pct", sa.Numeric(), nullable=False),
        sa.Column("observed_value_pct", sa.Numeric(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["threshold_id"], ["bond_alert_thresholds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bond_alert_events_instrument", "bond_alert_events", ["instrument"])

    op.create_table(
        "bond_collection_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("instruments_requested", sa.Integer(), nullable=False),
        sa.Column("instruments_succeeded", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("bond_collection_runs")
    op.drop_index("ix_bond_alert_events_instrument", table_name="bond_alert_events")
    op.drop_table("bond_alert_events")
    op.drop_table("bond_alert_thresholds")
    op.drop_index("ix_bond_yield_snapshots_observed_at", table_name="bond_yield_snapshots")
    op.drop_table("bond_yield_snapshots")
