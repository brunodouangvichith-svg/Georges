"""Réévalue les décisions existantes (`decisions`) au regard de l'historique
de prix réel et insère le résultat dans `decision_outcomes`. À lancer
manuellement pour l'instant (pas encore planifié).

Pour chaque décision, compare le plus haut/plus bas atteint depuis sa
création à ses niveaux de take-profit/stop-loss :
- take-profit atteint (`take_profit_hit`) si le prix a franchi ce niveau
  dans le sens favorable à la décision (le plus haut pour Achat/Renforcer,
  le plus bas pour Alléger),
- stop-loss atteint (`stop_loss_hit`) de façon symétrique,
- sinon la décision est toujours `open`, avec le rendement (%) courant
  (clôture actuelle vs prix d'entrée) comme `pnl_pct` indicatif.

Si les deux niveaux ont été franchis depuis la création (l'historique
quotidien ne permet pas de savoir dans quel ordre à l'intra-séance), celui
dont la première séance de franchissement est la plus ancienne l'emporte.

Usage :
    python -m engine.reevaluate_decisions
"""

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select

from engine.run_detection import load_prices
from ingestion.db import get_engine
from ingestion.models import Decision, DecisionOutcome

BULLISH_DECISIONS = {"Achat", "Renforcer"}


def evaluate_decision(decision, df: pd.DataFrame) -> tuple[str, float] | None:
    """`decision` : ligne de `decisions` (symbol, decision_type, entry_price,
    take_profit, stop_loss, created_at). Renvoie `(result, pnl_pct)`, ou
    `None` si aucune séance n'est disponible depuis la création."""
    since = df[df.index >= decision.created_at]
    if since.empty:
        return None

    bullish = decision.decision_type in BULLISH_DECISIONS
    entry = float(decision.entry_price)
    last_close = float(since["close"].iloc[-1])

    tp_hit_at = sl_hit_at = None
    if decision.take_profit is not None:
        tp = float(decision.take_profit)
        touch = since[since["high"] >= tp] if bullish else since[since["low"] <= tp]
        if not touch.empty:
            tp_hit_at = touch.index[0]
    if decision.stop_loss is not None:
        sl = float(decision.stop_loss)
        touch = since[since["low"] <= sl] if bullish else since[since["high"] >= sl]
        if not touch.empty:
            sl_hit_at = touch.index[0]

    direction = 1 if bullish else -1
    if tp_hit_at is not None and (sl_hit_at is None or tp_hit_at <= sl_hit_at):
        pnl = (float(decision.take_profit) - entry) / entry * 100 * direction
        return "take_profit_hit", pnl
    if sl_hit_at is not None:
        pnl = (float(decision.stop_loss) - entry) / entry * 100 * direction
        return "stop_loss_hit", pnl

    pnl = (last_close - entry) / entry * 100 * direction
    return "open", pnl


def run() -> int:
    """Réévalue toutes les décisions et insère un nouveau
    `decision_outcomes` pour chacune ayant au moins une séance de prix
    depuis sa création. Renvoie le nombre de lignes insérées."""
    engine = get_engine()
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        decisions = conn.execute(
            select(
                Decision.id,
                Decision.symbol,
                Decision.decision_type,
                Decision.entry_price,
                Decision.take_profit,
                Decision.stop_loss,
                Decision.created_at,
            )
        ).all()

    updated = 0
    for decision in decisions:
        df = load_prices(engine, decision.symbol)
        if df.empty:
            continue
        outcome = evaluate_decision(decision, df)
        if outcome is None:
            continue
        result, pnl_pct = outcome
        with engine.begin() as conn:
            conn.execute(
                DecisionOutcome.__table__.insert().values(
                    decision_id=decision.id, evaluated_at=now, result=result, pnl_pct=pnl_pct
                )
            )
        updated += 1
    return updated


if __name__ == "__main__":
    count = run()
    print(f"{count} décisions réévaluées et insérées dans decision_outcomes.")
