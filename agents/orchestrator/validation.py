"""Module de validation des informations collectées par les sous-agents
(Phase 7, tâche 4) — recoupement multi-sources, score de fiabilité, décision
validé/quarantaine. Pur : aucune DB, aucun réseau (même esprit que
`agents/context.py`) — `agents/orchestrator/run.py` est seul responsable
d'écrire le résultat en base."""

from __future__ import annotations

from dataclasses import dataclass

from agents.orchestrator.types import CollectedItem

SINGLE_SOURCE_RELIABILITY = 0.6
DEFAULT_TOLERANCE_PCT = 1.0


@dataclass
class ValidationOutcome:
    status: str  # "validated" | "quarantine"
    reliability_score: float
    description: str
    reason: str
    payload: dict
    symbol: str | None = None


def _item_payload(item: CollectedItem) -> dict:
    return {
        "source": item.source_name,
        "source_url": item.source_url,
        "value": item.value,
        "unit": item.unit,
        "observed_at": item.observed_at,
    }


def _format_single(label: str, item: CollectedItem) -> str:
    unit = item.unit or ""
    return f"{label} : {item.value}{unit} ({item.source_name}, {item.observed_at})"


def validate(
    label: str,
    items: list[CollectedItem],
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> ValidationOutcome:
    """`items` : un `CollectedItem` par source ayant répondu, toutes pour la
    même grandeur (`label`) — un sous-agent doit déjà avoir écarté les
    sources en échec réseau (voir `agents/collectors/macro.py`) avant
    d'appeler cette fonction. Une seule source → validée par défaut, score
    de fiabilité modéré (pas de fabrication d'une 2e source). Plusieurs
    sources dont les valeurs numériques s'accordent (écart relatif ≤
    `tolerance_pct`) → validée, score plus élevé. Sinon → quarantaine, avec
    le détail des valeurs par source dans `reason`. Renvoie toujours un
    verdict (jamais `None`) pour que l'appelant sache systématiquement où
    écrire le résultat."""
    if not items:
        raise ValueError(f"validate() appelé sans aucune source pour « {label} » — bug du collecteur appelant.")

    symbol = items[0].symbol
    payload = {"sources": [_item_payload(i) for i in items]}

    if len(items) == 1:
        return ValidationOutcome(
            status="validated",
            reliability_score=SINGLE_SOURCE_RELIABILITY,
            description=_format_single(label, items[0]),
            reason="Source unique — aucun recoupement indépendant disponible.",
            payload=payload,
            symbol=symbol,
        )

    values = [float(i.value) for i in items]
    mean_value = sum(values) / len(values)
    spread_pct = (max(values) - min(values)) / abs(mean_value) * 100 if mean_value else 0.0
    sources_text = ", ".join(f"{i.source_name} : {i.value}{i.unit or ''} ({i.observed_at})" for i in items)

    if spread_pct <= tolerance_pct:
        reliability_score = round(max(SINGLE_SOURCE_RELIABILITY, 1 - spread_pct / 100), 2)
        return ValidationOutcome(
            status="validated",
            reliability_score=reliability_score,
            description=f"{label} : {sources_text} — sources concordantes (écart {spread_pct:.2f}%).",
            reason=f"{len(items)} sources indépendantes concordent (écart {spread_pct:.2f}% ≤ {tolerance_pct}%).",
            payload=payload,
            symbol=symbol,
        )

    return ValidationOutcome(
        status="quarantine",
        reliability_score=0.0,
        description=f"{label} : sources contradictoires ({sources_text}).",
        reason=f"Écart de {spread_pct:.2f}% entre {len(items)} sources (seuil {tolerance_pct}%) — {sources_text}.",
        payload=payload,
        symbol=symbol,
    )
