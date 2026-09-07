"""ajoute la table company_news_knowledge (veille continue d'actualités entreprises pour George)

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024  # dimension de sortie du modèle mistral-embed (même modèle que jane_knowledge, migration 0014)


def upgrade() -> None:
    # L'extension vector existe déjà (migration 0004) — pas de CREATE EXTENSION ici.
    op.create_table(
        "company_news_knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        # Pas de ForeignKey vers securities.symbol : les entreprises
        # biocarburants/gaz renouvelables ciblées ici n'y ont pour la plupart
        # aucune ligne (voir ingestion/models.py:CompanyNewsKnowledge).
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_news_knowledge_symbol", "company_news_knowledge", ["symbol"])
    op.create_index("ix_company_news_knowledge_created_at", "company_news_knowledge", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_company_news_knowledge_created_at", table_name="company_news_knowledge")
    op.drop_index("ix_company_news_knowledge_symbol", table_name="company_news_knowledge")
    op.drop_table("company_news_knowledge")
