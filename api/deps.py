"""Dépendances FastAPI partagées.

Le moteur SQLAlchemy est créé une seule fois au chargement du module
(plutôt qu'à chaque requête) — `get_engine()` (`ingestion/db.py`) construit
un nouveau pool de connexions à chaque appel, ce qui serait coûteux et
inutile si répété à chaque requête HTTP.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from ingestion.db import get_engine

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
