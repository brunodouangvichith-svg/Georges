"""Génération de rapports automatiques (Phase 4, tâche 5) + indexation
pgvector (tâche 4) : le texte est généré par le LLM à partir de données
réelles, puis embeddé (`mistral-embed`) et stocké dans `reports` pour une
recherche sémantique complémentaire aux requêtes SQL directes de
`agents/chat.py`.

Réutilise directement `engine.george_index`/`engine.compute_george_index`
(Phase 2) pour le George Index d'un panier, sur le même principe que
`api/routers/baskets.py` : reçoit l'`Engine` en paramètre plutôt que
d'importer une référence figée, pour ne jamais rejouer le bug de référence
obsolète déjà rencontré (voir CLAUDE.md, section Phase 3)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client
from agents.context import basket_report_context
from engine.compute_george_index import load_patterns
from engine.george_index import compute_george_index
from engine.run_detection import load_prices
from ingestion.models import Basket, BasketSecurity, Decision, Report, Security


def _active_decisions(db: Session, symbols: list[str]) -> list[Decision]:
    if not symbols:
        return []
    stmt = select(Decision).where(Decision.symbol.in_(symbols)).order_by(Decision.created_at.desc())
    return db.execute(stmt).scalars().all()


def _basket_george_index(engine, symbols_weights: list[tuple[str, float]]) -> float | None:
    if not symbols_weights:
        return None
    patterns = load_patterns(engine)
    price_frames = {symbol: load_prices(engine, symbol) for symbol, _ in symbols_weights}
    price_frames = {symbol: df for symbol, df in price_frames.items() if not df.empty}
    return compute_george_index(symbols_weights, patterns, price_frames, datetime.now(timezone.utc))


def _build_context(db: Session, engine, basket_id: int | None) -> dict:
    if basket_id is not None:
        basket = db.get(Basket, basket_id)
        if basket is None:
            raise LookupError(f"Panier inconnu : {basket_id}")
        links = db.execute(select(BasketSecurity).where(BasketSecurity.basket_id == basket_id)).scalars().all()
        symbols_weights = [(link.symbol, float(link.weight) if link.weight is not None else 1.0) for link in links]
        george_index = _basket_george_index(engine, symbols_weights)
        decisions = _active_decisions(db, [s for s, _ in symbols_weights])
        return basket_report_context(basket, george_index, decisions, len(symbols_weights))

    # Rapport portefeuille (tous les paniers) : pas d'agrégat George Index
    # défini à cette échelle par la Phase 2 (le George Index est une notion
    # par panier, voir engine/george_index.md) — le rapport le laisse à None
    # plutôt que d'inventer une moyenne non spécifiée par la méthodologie.
    securities = db.execute(select(Security)).scalars().all()
    decisions = _active_decisions(db, [s.symbol for s in securities])
    return basket_report_context(None, None, decisions, len(securities))


def generate_report(db: Session, engine, basket_id: int | None = None) -> Report:
    context = _build_context(db, engine, basket_id)
    system_prompt = mistral_client.load_system_prompt("report_system.txt")
    user_message = json.dumps(context, ensure_ascii=False)
    content = mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)

    [embedding] = mistral_client.embed([content])
    report = Report(
        scope=f"basket:{basket_id}" if basket_id is not None else "portfolio",
        basket_id=basket_id,
        content=content,
        embedding=embedding,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def search_reports(db: Session, query: str, limit: int = 5) -> list[Report]:
    [query_embedding] = mistral_client.embed([query])
    stmt = select(Report).order_by(Report.embedding.cosine_distance(query_embedding)).limit(limit)
    return db.execute(stmt).scalars().all()
