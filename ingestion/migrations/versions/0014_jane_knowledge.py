"""ajoute la table jane_knowledge (Phase 7, veille méthodologique de Jane)

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024  # dimension de sortie du modèle mistral-embed (même modèle que `reports`, migration 0004)


def upgrade() -> None:
    # L'extension vector existe déjà (migration 0004) — pas de CREATE EXTENSION ici.
    op.create_table(
        "jane_knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jane_knowledge_created_at", "jane_knowledge", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_jane_knowledge_created_at", table_name="jane_knowledge")
    op.drop_table("jane_knowledge")
