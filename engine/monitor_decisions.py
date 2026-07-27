"""Job de suivi périodique des décisions confirmées — Phase 6, tâche 4.

Pour chaque décision `status == "confirmee"`, vérifie si le cours a atteint
le take-profit ou franchi le stop-loss (`engine.reevaluate_decisions.evaluate_decision`,
Phase 2) puis, le cas échéant, décide d'un scénario de sortie
(`engine.exit_scenarios.classify_exit`, distinction volume confirmé/bruit
sur un stop-loss) et en génère la justification textuelle
(`agents.explainer.explain_exit_scenario`, Phase 4).

Contrainte de la roadmap : ce job ne clôture jamais une position lui-même —
il fait passer la décision en `status="sortie_proposee"`, scénario et
justification déjà remplis, consultable via `GET /decisions/{id}`. Seule une
confirmation explicite via `POST /decisions/{id}/confirm-exit` écrit dans
`decision_outcomes` (tâche 5) et clôture réellement la décision.

Usage :
    python -m engine.monitor_decisions
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.explainer import explain_exit_scenario
from engine.exit_scenarios import classify_exit
from engine.reevaluate_decisions import evaluate_decision
from engine.run_detection import load_prices
from ingestion.db import get_engine
from ingestion.models import Decision


def run() -> list[dict]:
    engine = get_engine()
    proposed = []

    with Session(engine) as db:
        decisions = db.execute(select(Decision).where(Decision.status == "confirmee")).scalars().all()

        for decision in decisions:
            df = load_prices(engine, decision.symbol)
            if df.empty:
                continue
            outcome = evaluate_decision(decision, df)
            if outcome is None:
                continue
            result, pnl_pct, hit_at = outcome
            if result == "open":
                continue

            hit_idx = int(df.index.get_indexer([hit_at], method="nearest")[0])
            scenario, volume_confirmed = classify_exit(result, df["volume"], hit_idx)
            justification = explain_exit_scenario(db, decision, result, pnl_pct, scenario, volume_confirmed)

            decision.exit_scenario = scenario
            decision.exit_volume_confirmed = volume_confirmed
            decision.exit_justification = justification
            decision.exit_proposed_at = datetime.now(timezone.utc)
            decision.status = "sortie_proposee"
            db.commit()

            proposed.append(
                {"id": decision.id, "symbol": decision.symbol, "scenario": scenario, "pnl_pct": round(pnl_pct, 2)}
            )

    return proposed


if __name__ == "__main__":
    proposals = run()
    if not proposals:
        print("Aucune décision confirmée n'a franchi son take-profit/stop-loss.")
    else:
        for p in proposals:
            print(
                f"{p['symbol']:10s} {p['scenario']:18s} pnl {p['pnl_pct']:+.2f}% "
                f"-> sortie_proposee (décision {p['id']})"
            )
