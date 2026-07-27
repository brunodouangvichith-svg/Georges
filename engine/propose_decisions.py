"""Propose des décisions (Achat/Alléger) à partir des figures détectées
récentes à forte confiance — Phase 6.

La roadmap (tâche 1-2) part du principe que des lignes `decisions` existent
déjà et ne précise que le calcul des niveaux de sortie ; en réalité, avant
cette phase, seul `ingestion/seed_demo.py` insérait des décisions, de façon
explicitement illustrative (voir CLAUDE.md, Phase 3). Ce module ferme cet
écart : chaque proposition part d'une figure réelle détectée par le moteur
(Phase 1), avec ses niveaux de sortie calculés par `engine/exit_levels.py`
— rien n'est confirmé ni exécuté automatiquement (`status="proposee"`),
conformément au principe "George propose, l'investisseur valide" rappelé
par la contrainte de la Phase 6.

`select_candidates` est pur (pas d'accès DB, testé sur des listes
construites à la main) ; `run`/`recompute_levels` font le lien avec la base,
sur le même principe de séparation que `engine/reevaluate_decisions.py`
(qui mélange déjà une fonction pure et un script DB dans un seul fichier).

Usage :
    python -m engine.propose_decisions
"""
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select

from engine.exit_levels import is_bullish, propose_levels
from engine.run_detection import load_prices
from ingestion.db import get_engine
from ingestion.models import Decision, PatternDetected

MIN_PROPOSAL_CONFIDENCE = 50.0
ACTIVE_WINDOW_SESSIONS = 5  # même fenêtre que engine.george_index.ACTIVE_WINDOW_SESSIONS
OPEN_STATUSES = ("proposee", "confirmee", "sortie_proposee")


def _is_active(detected_at, as_of, window_sessions: int = ACTIVE_WINDOW_SESSIONS) -> bool:
    cutoff = as_of - pd.Timedelta(days=window_sessions * 1.5)  # marge week-ends/jours fériés
    return cutoff < detected_at <= as_of


def select_candidates(
    patterns: list,
    existing_open_symbols: set,
    as_of,
    min_confidence: float = MIN_PROPOSAL_CONFIDENCE,
) -> dict:
    """`patterns` : lignes avec `.symbol`, `.pattern_type`, `.detected_at`,
    `.confidence` (et tout attribut additionnel que l'appelant veut
    récupérer sur le résultat, ex. `.id`, `.context`). Pour chaque symbole
    sans décision déjà ouverte, renvoie la figure active la plus confiante
    au-delà de `min_confidence` — au plus une proposition par symbole à la
    fois, pour ne pas empiler des signaux potentiellement contradictoires."""
    best: dict = {}
    for p in patterns:
        if p.symbol in existing_open_symbols or p.confidence < min_confidence:
            continue
        if not _is_active(p.detected_at, as_of):
            continue
        current = best.get(p.symbol)
        if current is None or p.confidence > current.confidence:
            best[p.symbol] = p
    return best


def recompute_levels(engine, symbol: str, pattern_type: str, context: dict) -> tuple[float, float]:
    """Recalcule (take_profit, stop_loss) sur le prix le plus récent
    disponible — utilisé à la création d'une proposition et par
    `POST /decisions/{id}/propose-levels` (tâche 2) pour rafraîchir des
    niveaux déjà proposés avant confirmation."""
    df = load_prices(engine, symbol)
    entry_price = float(df["close"].iloc[-1])
    take_profit, stop_loss = propose_levels(pattern_type, context, entry_price, df)
    return round(take_profit, 2), round(stop_loss, 2)


def run(as_of=None) -> list[dict]:
    engine = get_engine()
    as_of = as_of or datetime.now(timezone.utc)

    with engine.begin() as conn:
        patterns = conn.execute(
            select(
                PatternDetected.id,
                PatternDetected.symbol,
                PatternDetected.pattern_type,
                PatternDetected.detected_at,
                PatternDetected.confidence,
                PatternDetected.context,
            )
        ).all()
        open_symbols = {
            row.symbol for row in conn.execute(select(Decision.symbol).where(Decision.status.in_(OPEN_STATUSES)))
        }

    candidates = select_candidates(patterns, open_symbols, as_of)

    created = []
    for symbol, pattern in candidates.items():
        df = load_prices(engine, symbol)
        if df.empty:
            continue
        entry_price = float(df["close"].iloc[-1])
        try:
            take_profit, stop_loss = propose_levels(pattern.pattern_type, pattern.context, entry_price, df)
        except KeyError:
            continue  # type de figure non géré par exit_levels — ne devrait pas arriver

        with engine.begin() as conn:
            decision_id = conn.execute(
                Decision.__table__.insert()
                .values(
                    symbol=symbol,
                    pattern_id=pattern.id,
                    decision_type="Achat" if is_bullish(pattern.pattern_type) else "Alléger",
                    status="proposee",
                    entry_price=entry_price,
                    take_profit=round(take_profit, 2),
                    stop_loss=round(stop_loss, 2),
                    confidence=float(pattern.confidence),
                    rationale=None,  # la justification détaillée vit derrière /decisions/{id}/explanation (Phase 4)
                )
                .returning(Decision.id)
            ).scalar_one()

        created.append(
            {
                "id": decision_id,
                "symbol": symbol,
                "pattern_type": pattern.pattern_type,
                "decision_type": "Achat" if is_bullish(pattern.pattern_type) else "Alléger",
                "entry_price": entry_price,
                "take_profit": round(take_profit, 2),
                "stop_loss": round(stop_loss, 2),
                "confidence": float(pattern.confidence),
            }
        )
    return created


if __name__ == "__main__":
    proposals = run()
    if not proposals:
        print("Aucune nouvelle proposition (pas de figure active assez confiante sans décision déjà ouverte).")
    else:
        for p in proposals:
            print(
                f"{p['symbol']:10s} {p['decision_type']:8s} ({p['pattern_type']}, {p['confidence']:.1f}%) "
                f"entrée {p['entry_price']:.2f}  TP {p['take_profit']:.2f}  SL {p['stop_loss']:.2f}"
            )
