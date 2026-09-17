"""Orchestrateur de collecte (Phase 7, MVP, tâche 1) — dispatche une tâche
de collecte (`task_type`) vers le sous-agent correspondant
(`agents/collectors/`), valide chaque grandeur collectée
(`agents/orchestrator/validation.py`), et écrit le résultat en base :
`AgentEvent` si validée, `CollectedInfoQuarantine` sinon. `engine` est reçu
en paramètre (jamais importé au niveau module) — même précaution
anti-référence-obsolète que `agents/reports.py`/`api/routers/portfolios.py`.

Pour les sous-agents dont la grandeur est un vrai indicateur numérique
(`NUMERIC_INDICATOR_TASK_TYPES`), un groupe validé est aussi upserté dans
`ingestion.models.MacroIndicatorSnapshot` — une vraie table interrogeable
dans le temps, en plus de `AgentEvent` (toujours écrit, pour le flux
d'activité). Jamais pour une quarantaine : une donnée contradictoire
n'entre jamais dans cette table."""

from __future__ import annotations

from typing import Callable

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from agents.orchestrator.validation import validate
from ingestion.models import AgentEvent, CollectedInfoQuarantine, MacroIndicatorSnapshot

# Sous-agents dont la grandeur collectée est un vrai nombre (taux, indice,
# montant), assez stable pour mériter une vraie table interrogeable dans le
# temps (voir `ingestion/models.py:MacroIndicatorSnapshot`) plutôt que de
# rester noyée dans `agent_events`. `synthese_document` en est délibérément
# exclu : son `CollectedItem.value` est un résumé texte, pas un nombre.
NUMERIC_INDICATOR_TASK_TYPES = {"donnees_macro", "donnees_eurostat", "donnees_tic", "donnees_worldbank"}


def _upsert_indicator_snapshots(db: Session, label: str, items, reliability_score: float) -> None:
    """Un instantané par `CollectedItem` (pas juste par groupe/indicateur) :
    un même indicateur peut avoir plusieurs sources indépendantes par cycle
    (ex. EUR/USD via FRED+BCE+Frankfurter) — chacune garde sa propre valeur
    plutôt que de s'écraser mutuellement, voir la clé unique du modèle.
    `reliability_score` vient de `ValidationOutcome` (une seule valeur pour
    tout le groupe, pas par source). Utilise le `label` du groupe (celui
    passé à `validate()`), pas `item.label` : chaque collecteur passe déjà le
    même `label` à ses fetchers en production, mais rien ne garantit que
    `CollectedItem.label` reste fidèle à ça (un `CollectedItem` construit à
    la main, ex. dans un test, peut s'en écarter) — le `label` du groupe est
    la seule source de vérité pour "quel indicateur est-ce"."""
    for item in items:
        stmt = pg_insert(MacroIndicatorSnapshot).values(
            indicator=label,
            value=float(item.value),
            unit=item.unit,
            source_name=item.source_name,
            observed_at=item.observed_at,
            reliability_score=reliability_score,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                MacroIndicatorSnapshot.indicator,
                MacroIndicatorSnapshot.source_name,
                MacroIndicatorSnapshot.observed_at,
            ],
            set_={"value": stmt.excluded.value, "reliability_score": stmt.excluded.reliability_score},
        )
        db.execute(stmt)


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
            if task_type in NUMERIC_INDICATOR_TASK_TYPES:
                _upsert_indicator_snapshots(db, label, items, outcome.reliability_score)
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
