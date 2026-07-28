"""Type partagé entre les sous-agents de collecte (`agents/collectors/`) et
le module de validation (`agents/orchestrator/validation.py`). Aucun réseau,
aucune DB — pur, comme `agents/context.py`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CollectedItem:
    """Une valeur observée par un sous-agent, pour une source donnée. Une
    même grandeur (ex. "Taux de change EUR/USD") peut être collectée par
    plusieurs sources indépendantes — chacune produit un `CollectedItem`
    séparé, regroupés par le collecteur avant validation."""

    label: str
    value: float | str
    unit: str | None
    source_name: str
    source_url: str | None
    observed_at: str  # date/heure ISO de l'observation elle-même, pas de la collecte
    symbol: str | None = None
