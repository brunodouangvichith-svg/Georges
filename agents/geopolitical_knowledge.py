"""Base de connaissances géopolitiques/économiques par pays pour George
("pilier 7" du roadmap, Phase 7 — voir `whitelist_journaux.md`/`.json`) —
même infrastructure que `agents/company_knowledge.py` (embedding
`mistral-embed` + pgvector + dédup par similarité), mais scopée par pays
(`country`) plutôt que par entreprise. Voir
`ingestion/models.py:GeopoliticalKnowledge` pour le choix de schéma et
`agents/geopolitical_veille.py` pour l'alimentation continue.

`add_geopolitical_knowledge` déduplique par similarité UNIQUEMENT au sein
du même pays (`WHERE country = ...`), même raisonnement que
`company_knowledge.add_company_knowledge` : deux actualités sans rapport
concernant deux pays différents ne doivent jamais s'écraser l'une l'autre
au motif d'une similarité de formulation accidentelle.

`search_geopolitical_knowledge` (consommée par `agents.chat.answer_question`)
est une recherche sémantique, PAS un filtre par récence comme
`company_knowledge.get_recent_company_knowledge` — contrairement au chemin
entreprise, `/chat` n'a aucune détection de pays dans la question (pas de
`find_relevant_securities`-équivalent), donc c'est la similarité
embedding↔question qui doit faire remonter le bon pays plutôt qu'un filtre
exact préalable."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from ingestion.models import GeopoliticalKnowledge

# Même seuil que `agents/company_knowledge.py`/`agents/jane_knowledge.py`
# (distance cosinus pgvector en dessous de laquelle un contenu est un
# quasi-doublon, similarité >= 0.95).
DEDUP_DISTANCE_THRESHOLD = 0.05


def add_geopolitical_knowledge(
    db: Session,
    content: str,
    country: str,
    region: str | None = None,
    source_name: str = "",
    source_url: str | None = None,
    dedup_distance_threshold: float = DEDUP_DISTANCE_THRESHOLD,
) -> GeopoliticalKnowledge | None:
    """Embedde `content` et l'ajoute à `geopolitical_knowledge`, sauf quasi-
    doublon déjà présent pour le MÊME pays (voir docstring du module), auquel
    cas renvoie `None` sans rien écrire."""
    [embedding] = mistral_client.embed([content])

    distance = GeopoliticalKnowledge.embedding.cosine_distance(embedding).label("distance")
    nearest = db.execute(
        select(GeopoliticalKnowledge.id, distance).where(GeopoliticalKnowledge.country == country).order_by(distance).limit(1)
    ).first()
    if nearest is not None and nearest.distance <= dedup_distance_threshold:
        return None

    entry = GeopoliticalKnowledge(
        country=country,
        region=region,
        content=content,
        source_name=source_name,
        source_url=source_url,
        embedding=embedding,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def search_geopolitical_knowledge(
    db: Session, query: str, limit: int = 3, query_embedding: list[float] | None = None
) -> list[GeopoliticalKnowledge]:
    """Recherche sémantique dans `geopolitical_knowledge`, même principe que
    `agents/jane_knowledge.py:search_jane_knowledge` — utilisée par
    `agents.chat.answer_question` pour injecter le contexte géopolitique le
    plus pertinent, sans détection de pays préalable dans la question.

    `query_embedding` est optionnel (calculé à partir de `query` si absent) —
    voir `search_jane_knowledge` pour le raisonnement (évite un appel Mistral
    redondant quand `/chat` interroge cette base et `jane_knowledge` pour la
    même question)."""
    if query_embedding is None:
        [query_embedding] = mistral_client.embed([query])
    stmt = select(GeopoliticalKnowledge).order_by(GeopoliticalKnowledge.embedding.cosine_distance(query_embedding)).limit(limit)
    return db.execute(stmt).scalars().all()
