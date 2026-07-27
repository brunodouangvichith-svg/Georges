"""Constructeurs de contexte structuré pour les appels LLM de George (Phase 4)
— pur, sans accès DB, sur le même principe que `engine/backtest.py` vis-à-vis
de `engine/build_training_set.py` : ces fonctions prennent des objets déjà
récupérés (ORM ou valeurs simples) et rendent un dict JSON-sérialisable,
jamais de requête SQL ici. C'est ce dict, et rien d'autre, qui est envoyé au
LLM en message utilisateur — le prompt système interdit d'utiliser un chiffre
absent de ce contexte, donc tout ce qui doit être citable doit y figurer.

`Numeric` (SQLAlchemy) revient en `decimal.Decimal` : converti en `float` ici
pour que le contexte soit directement sérialisable en JSON.
"""
from __future__ import annotations

from ingestion.models import Basket, Decision, PatternDetected, Security


def decision_context(
    decision: Decision,
    pattern: PatternDetected | None,
    security: Security,
    jane_note: str | None = None,
) -> dict:
    context: dict = {
        "titre": {
            "symbole": security.symbol,
            "nom": security.name,
            "secteur": security.sector,
        },
        "decision": {
            "type": decision.decision_type,
            "prix_entree": float(decision.entry_price),
            "take_profit": float(decision.take_profit) if decision.take_profit is not None else None,
            "stop_loss": float(decision.stop_loss) if decision.stop_loss is not None else None,
            "confiance": float(decision.confidence),
        },
        "pattern": None,
        "jane_note": jane_note,
    }
    if pattern is not None:
        context["pattern"] = {
            "type": pattern.pattern_type,
            "detecte_le": pattern.detected_at.isoformat(),
            "confiance": float(pattern.confidence),
        }
    return context


def security_snapshot(
    security: Security,
    latest_decision: Decision | None,
    latest_pattern: PatternDetected | None,
) -> dict:
    """Instantané d'un titre pour le RAG SQL simple de `/chat` (tâche 3) —
    une entrée par titre reconnu dans la question posée."""
    snapshot: dict = {
        "symbole": security.symbol,
        "nom": security.name,
        "secteur": security.sector,
        "derniere_decision": None,
        "derniere_figure": None,
    }
    if latest_decision is not None:
        snapshot["derniere_decision"] = {
            "type": latest_decision.decision_type,
            "prix_entree": float(latest_decision.entry_price),
            "take_profit": float(latest_decision.take_profit) if latest_decision.take_profit is not None else None,
            "stop_loss": float(latest_decision.stop_loss) if latest_decision.stop_loss is not None else None,
            "confiance": float(latest_decision.confidence),
        }
    if latest_pattern is not None:
        snapshot["derniere_figure"] = {
            "type": latest_pattern.pattern_type,
            "detecte_le": latest_pattern.detected_at.isoformat(),
            "confiance": float(latest_pattern.confidence),
        }
    return snapshot


def exit_scenario_context(
    decision: Decision,
    security: Security,
    result: str,
    pnl_pct: float,
    scenario: str,
    volume_confirmed: bool | None,
) -> dict:
    """Contexte pour `agents/explainer.py:explain_exit_scenario` (Phase 6,
    tâche 4) — `result`/`scenario`/`volume_confirmed` viennent déjà décidés
    par `engine.exit_scenarios.classify_exit`, jamais recalculés ici ou par
    le LLM : ce module ne fait que les mettre en mots."""
    return {
        "titre": {"symbole": security.symbol, "nom": security.name},
        "decision": {
            "type": decision.decision_type,
            "prix_entree": float(decision.entry_price),
            "take_profit": float(decision.take_profit) if decision.take_profit is not None else None,
            "stop_loss": float(decision.stop_loss) if decision.stop_loss is not None else None,
        },
        "resultat": result,
        "pnl_pct": round(pnl_pct, 2),
        "scenario_propose": scenario,
        "confirme_par_volume": volume_confirmed,
    }


def basket_report_context(
    basket: Basket | None,
    george_index: float | None,
    decisions: list[Decision],
    security_count: int,
) -> dict:
    """`basket=None` désigne un rapport portefeuille (tous les paniers), pas
    un panier particulier — voir `agents/reports.py:generate_report`."""
    return {
        "perimetre": {"type": "panier", "nom": basket.name} if basket is not None else {"type": "portefeuille"},
        "nombre_titres": security_count,
        "george_index": george_index,
        "decisions_actives": [
            {
                "symbole": d.symbol,
                "type": d.decision_type,
                "confiance": float(d.confidence),
            }
            for d in decisions
        ],
    }
