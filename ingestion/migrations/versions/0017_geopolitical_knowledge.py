"""ajoute la table geopolitical_knowledge (veille continue d'actualités géopolitiques par pays, pilier 7)

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024  # dimension de sortie du modèle mistral-embed (même modèle que jane_knowledge/company_news_knowledge)


def upgrade() -> None:
    # L'extension vector existe déjà (migration 0004) — pas de CREATE EXTENSION ici.
    op.create_table(
        "geopolitical_knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geopolitical_knowledge_country", "geopolitical_knowledge", ["country"])
    op.create_index("ix_geopolitical_knowledge_created_at", "geopolitical_knowledge", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_geopolitical_knowledge_created_at", table_name="geopolitical_knowledge")
    op.drop_index("ix_geopolitical_knowledge_country", table_name="geopolitical_knowledge")
    op.drop_table("geopolitical_knowledge")
