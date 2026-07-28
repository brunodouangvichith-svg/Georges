"""Orchestrateur de collecte (Phase 7, MVP, tâche 1) — dispatche une tâche
de collecte (`task_type`) vers le sous-agent correspondant
(`agents/collectors/`), valide chaque grandeur collectée
(`agents/orchestrator/validation.py`), et écrit le résultat en base :
`AgentEvent` si validée, `CollectedInfoQuarantine` sinon. `engine` est reçu
en paramètre (jamais importé au niveau module) — même précaution
anti-référence-obsolète que `agents/reports.py`/`api/routers/portfolios.py`."""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from agents.orchestrator.validation import validate
from ingestion.models import AgentEvent, CollectedInfoQuarantine


def run_collection_task(
    db: Session, engine, task_type: str, collector: Callable, scope: dict | None = None
) -> dict:
    """`collector` est déjà résolu par l'appelant (`agents.collectors.COLLECTORS[task_type]`,
    voir `api/routers/agents.py`) — pas importé ici, pour que ce module
    générique n'ait pas à connaître le registre des sous-agents (et pour
    éviter un import circulaire `orchestrator` ↔ `collectors`, puisque les
    collecteurs importent eux-mêmes `agents.orchestrator.types`). `scope`
    est spécifique au sous-agent (ex. `{"report_id": ...}` pour
    `synthese_document`, `None` pour `donnees_macro`). Lève `ValueError`
    pour un `scope` invalide — l'appelant HTTP (`api/routers/agents.py`) le
    traduit en 404."""
    groups = collector(db, engine, scope)

    validated_events = []
    quarantined_count = 0

    for label, items in groups:
        outcome = validate(label, items)
        if outcome.status == "validated":
            event = AgentEvent(
                agent_name=task_type,
                description=outcome.description,
                status="validated",
                symbol=outcome.symbol,
                context={"reliability_score": outcome.reliability_score, **outcome.payload},
            )
            db.add(event)
            validated_events.append(event)
        else:
            db.add(
                CollectedInfoQuarantine(
                    agent_name=task_type,
                    task_type=task_type,
                    symbol=outcome.symbol,
                    description=outcome.description,
                    payload=outcome.payload,
                    reason=outcome.reason,
                )
            )
            quarantined_count += 1

    db.commit()
    return {"validated": validated_events, "quarantined_count": quarantined_count}
