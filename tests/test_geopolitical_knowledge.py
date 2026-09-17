"""Tests de `agents/geopolitical_knowledge.py`. `add_geopolitical_knowledge`/
`search_geopolitical_knowledge` ont besoin d'un vrai Postgres+pgvector
(testcontainers, fixture `database_url` — nécessite Docker, comme
`tests/test_jane_knowledge.py`)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import agents.mistral_client as mistral_client
from agents.geopolitical_knowledge import add_geopolitical_knowledge, search_geopolitical_knowledge


def _fake_embed_factory():
    """Même principe que `tests/test_jane_knowledge.py:_fake_embed_factory` --
    chaque texte *distinct* reçoit un vecteur one-hot différent, nécessaire
    pour exercer réellement la déduplication par similarité cosinus."""
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


def test_add_geopolitical_knowledge_then_search_roundtrip(database_url, monkeypatch):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(mistral_client, "embed", _fake_embed_factory())
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            entry = add_geopolitical_knowledge(
                db, content="Tensions commerciales en hausse.", country="France", region="Europe & UK", source_name="Test"
            )
            assert entry is not None
            assert entry.id is not None
            assert entry.country == "France"

            results = search_geopolitical_knowledge(db, "Tensions commerciales en hausse.", limit=5)
            assert results[0].content == "Tensions commerciales en hausse."
    finally:
        command.downgrade(cfg, "base")


def test_add_geopolitical_knowledge_skips_near_duplicate_within_the_same_country(database_url, monkeypatch):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(mistral_client, "embed", _fake_embed_factory())
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            first = add_geopolitical_knowledge(db, content="Contenu A", country="France", source_name="Test")
            assert first is not None

            # Même texte exact, même pays -> même vecteur -> distance 0 -> quasi-doublon ignoré.
            duplicate = add_geopolitical_knowledge(db, content="Contenu A", country="France", source_name="Test (relu)")
            assert duplicate is None
    finally:
        command.downgrade(cfg, "base")


def test_add_geopolitical_knowledge_does_not_dedupe_across_different_countries(database_url, monkeypatch):
    """Régression ciblée : deux actualités sans rapport concernant deux pays
    différents ne doivent jamais s'écraser l'une l'autre au motif d'une
    similarité de formulation accidentelle — même contenu texte, mais un
    pays différent doit être traité comme une entrée distincte (voir
    docstring du module, même raisonnement que
    `agents/company_knowledge.py`)."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    try:
        monkeypatch.setattr(mistral_client, "embed", _fake_embed_factory())
        engine = create_engine(database_url, future=True)
        session_factory = sessionmaker(bind=engine, future=True)
        with session_factory() as db:
            france_entry = add_geopolitical_knowledge(db, content="Contenu identique", country="France", source_name="Test")
            assert france_entry is not None

            germany_entry = add_geopolitical_knowledge(db, content="Contenu identique", country="Allemagne", source_name="Test")
            assert germany_entry is not None
            assert germany_entry.id != france_entry.id
    finally:
        command.downgrade(cfg, "base")
