"""Base de connaissances d'actualités entreprises pour George (ad hoc, pas
une phase du roadmap) — même infrastructure que `agents/jane_knowledge.py`
(embedding `mistral-embed` + pgvector + dédup par similarité), mais scopée
par entreprise (`company_name`/`symbol`) plutôt que par savoir méthodologique
général. Voir `ingestion/models.py:CompanyNewsKnowledge` pour le choix de
schéma et `agents/george_veille.py` pour l'alimentation continue.

`add_company_knowledge` déduplique par similarité UNIQUEMENT au sein de la
même entreprise (`WHERE symbol = ... OR company_name = ...`), contrairement
à `jane_knowledge.add_knowledge` qui compare contre toute la table — deux
actualités sans rapport concernant deux entreprises différentes ne doivent
jamais s'écraser l'une l'autre au motif d'une similarité de formulation
accidentelle ("le titre a publié ses résultats trimestriels..." se ressemble
d'une entreprise à l'autre sans être un vrai doublon).

`get_recent_company_knowledge` (consommée par `agents.chat.answer_question`)
est une simple requête filtrée par récence, pas une recherche par similarité
— on veut "les actualités les plus récentes pour cette entreprise", pas
"les actualités les plus proches sémantiquement d'une question" ; ça évite
aussi un appel `mistral_client.embed` supplémentaire sur le chemin `/chat`,
qui reste ainsi aussi rapide qu'avant cet ajout."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from agents import mistral_client
from ingestion.models import CompanyNewsKnowledge

# Même seuil que `agents/jane_knowledge.py:DEDUP_DISTANCE_THRESHOLD` — même
# raisonnement (distance cosinus pgvector en dessous de laquelle un contenu
# est un quasi-doublon, similarité ≥ 0.95).
DEDUP_DISTANCE_THRESHOLD = 0.05


def add_company_knowledge(
    db: Session,
    content: str,
    company_name: str,
    symbol: str | None = None,
    source_name: str = "",
    source_url: str | None = None,
    dedup_distance_threshold: float = DEDUP_DISTANCE_THRESHOLD,
) -> CompanyNewsKnowledge | None:
    """Embedde `content` et l'ajoute à `company_news_knowledge`, sauf quasi-
    doublon déjà présent pour la MÊME entreprise (voir docstring du module),
    auquel cas renvoie `None` sans rien écrire."""
    [embedding] = mistral_client.embed([content])

    distance = CompanyNewsKnowledge.embedding.cosine_distance(embedding).label("distance")
    same_company = or_(CompanyNewsKnowledge.symbol == symbol, CompanyNewsKnowledge.company_name == company_name) if symbol else (CompanyNewsKnowledge.company_name == company_name)
    nearest = db.execute(select(CompanyNewsKnowledge.id, distance).where(same_company).order_by(distance).limit(1)).first()
    if nearest is not None and nearest.distance <= dedup_distance_threshold:
        return None

    entry = CompanyNewsKnowledge(
        company_name=company_name,
        symbol=symbol,
        content=content,
        source_name=source_name,
        source_url=source_url,
        embedding=embedding,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_recent_company_knowledge(
    db: Session, symbol: str | None = None, company_name: str | None = None, limit: int = 3
) -> list[CompanyNewsKnowledge]:
    """Actualités les plus récentes pour une entreprise — au moins l'un de
    `symbol`/`company_name` est requis. `symbol` est prioritaire quand les
    deux sont fournis (correspondance exacte fiable pour un titre suivi),
    `company_name` sert de repli pour les entreprises hors référentiel
    `securities` (ex. secteur biocarburants/gaz renouvelables, sans
    `symbol`)."""
    if not symbol and not company_name:
        raise ValueError("get_recent_company_knowledge requiert symbol et/ou company_name.")
    stmt = select(CompanyNewsKnowledge)
    stmt = stmt.where(CompanyNewsKnowledge.symbol == symbol) if symbol else stmt.where(CompanyNewsKnowledge.company_name == company_name)
    stmt = stmt.order_by(CompanyNewsKnowledge.created_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()
