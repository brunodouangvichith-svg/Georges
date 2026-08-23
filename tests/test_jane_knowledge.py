"""Tests de `agents/jane_knowledge.py`. `chunk_markdown` est pur (aucune
DB/réseau) ; `add_knowledge`/`search_jane_knowledge` ont besoin d'un vrai
Postgres+pgvector (testcontainers, fixture `database_url` -- nécessite
Docker, comme `tests/test_migrations.py`/`test_seed.py`)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import agents.mistral_client as mistral_client
from agents.jane_knowledge import add_knowledge, chunk_markdown, search_jane_knowledge

SAMPLE_MARKDOWN = """# Jane -- Synthese

Texte d'introduction avant tout titre de niveau 2, jamais un chunk exploitable.

## 1. Section simple

Contenu de la section 1, sans sous-titre.

## 2. Section avec sous-titres

Un paragraphe d'introduction avant la premiere sous-section.

### 2.1 Premiere sous-section

Contenu 2.1.

### 2.2 Deuxieme sous-section

Contenu 2.2.

## 3. Derniere section

Contenu de la section 3.
"""


def test_chunk_markdown_splits_simple_sections_by_level2_header():
    chunks = dict(chunk_markdown(SAMPLE_MARKDOWN))
    assert chunks["1. Section simple"] == "Contenu de la section 1, sans sous-titre."
    assert chunks["3. Derniere section"] == "Contenu de la section 3."


def test_chunk_markdown_splits_long_section_by_level3_header():
    chunks = dict(chunk_markdown(SAMPLE_MARKDOWN))
    assert chunks["2.1 Premiere sous-section"] == "Contenu 2.1."
    assert chunks["2.2 Deuxieme sous-section"] == "Contenu 2.2."
    # Le paragraphe d'intro avant "### 2.1" reste rattaché au titre de la section 2 (pas perdu).
    assert chunks["2. Section avec sous-titres"] == "Un paragraphe d'introduction avant la premiere sous-section."


def test_chunk_markdown_ignores_text_before_first_level2_header():
    chunks = dict(chunk_markdown(SAMPLE_MARKDOWN))
    assert "Jane -- Synthese" not in chunks
    assert not any("jamais un chunk exploitable" in body for body in chunks.values())


def test_chunk_markdown_empty_document_returns_no_chunks():
    assert chunk_markdown("") == []


def _fake_embed_factory():
    """Contrairement à `tests/test_api.py:_fake_embed` (volontairement
    uniforme, un vecteur nul pour tout texte), chaque texte *distinct* reçoit
    ici un vecteur one-hot différent — nécessaire pour exercer réellement la
    déduplication par similarité cosinus (deux textes identiques doivent
    retomber sur le même vecteur, deux textes différents sur des vecteurs
    orthogonaux)."""
    seen: dict[str, list[float]] = {}

    def _embed(texts, model=None):
        from ingestion.models import EMBEDDING_DIM

        vectors = []
        for text in texts:
            if text not in seen:
                index = len(seen)
                vector = [0.0] * EMBEDDING_DIM
                vector[index % EMBEDDING_DIM] = 1.0
                seen[text] = vector
            vectors.append(seen[text])
        return vectors

    return _embed


def test_add_knowledge_then_search_roundtrip(database_url, monkeypatch):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(mistral_client, "embed", _fake_embed_factory())
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            entry = add_knowledge(db, content="Le ratio de Sharpe mesure le rendement ajusté au risque.", source_name="Test")
            assert entry is not None
            assert entry.id is not None

            results = search_jane_knowledge(db, "Le ratio de Sharpe mesure le rendement ajusté au risque.", limit=5)
            assert results[0].content == "Le ratio de Sharpe mesure le rendement ajusté au risque."
    finally:
        command.downgrade(cfg, "base")


def test_add_knowledge_skips_near_duplicate_content(database_url, monkeypatch):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(mistral_client, "embed", _fake_embed_factory())
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            first = add_knowledge(db, content="Contenu A", source_name="Investopedia")
            assert first is not None

            # Même texte exact -> même vecteur (le fake le mémorise par texte) -> distance 0 -> quasi-doublon ignoré.
            duplicate = add_knowledge(db, content="Contenu A", source_name="Investopedia (relu une 2e fois)")
            assert duplicate is None

            second = add_knowledge(db, content="Contenu B, vraiment différent.", source_name="TradingView")
            assert second is not None
            assert second.id != first.id
    finally:
        command.downgrade(cfg, "base")
