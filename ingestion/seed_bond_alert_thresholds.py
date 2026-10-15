"""Amorce les 3 seuils d'alerte initiaux d'Obligataire Watch (ad hoc, pas une
phase du roadmap) dans `bond_alert_thresholds` — valeurs indicatives du
cahier des charges §8, pas des prédictions ni des recommandations
financières. Idempotent par une vraie contrainte DB (`uq_bond_alert_threshold
_instrument_direction`, migration `0018`) + `ON CONFLICT DO NOTHING` — pas
un `SELECT` puis `INSERT` séparés, qui laisserait une fenêtre de course entre
deux exécutions concurrentes (ex. deux processus de démarrage) créer un
doublon. Ne modifie jamais un seuil déjà présent : une valeur changée via
l'API (`PATCH /bonds/alerts/thresholds/{id}`) n'est donc jamais écrasée par
un relancement de ce script.

Usage :
    python -m ingestion.seed_bond_alert_thresholds
"""

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import (
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS,
    BOND_INSTRUMENT_UST_US_10Y,
    BondAlertThreshold,
)

# (instrument, direction, seuil) — voir le docstring de
# `ingestion.models.BondAlertThreshold` : le seuil du spread est en points
# de base, les deux autres en pourcentage.
DEFAULT_THRESHOLDS = [
    (BOND_INSTRUMENT_OAT_FR_10Y, "above", 4.90),
    (BOND_INSTRUMENT_UST_US_10Y, "above", 5.30),
    (BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS, "above", 150.0),
]


def seed_bond_alert_thresholds() -> int:
    engine = get_engine()
    created = 0
    with engine.begin() as conn:
        for instrument, direction, threshold_pct in DEFAULT_THRESHOLDS:
            stmt = pg_insert(BondAlertThreshold).values(
                instrument=instrument, direction=direction, threshold_pct=threshold_pct, enabled=True
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[BondAlertThreshold.instrument, BondAlertThreshold.direction]
            )
            result = conn.execute(stmt)
            created += result.rowcount
    return created


if __name__ == "__main__":
    n = seed_bond_alert_thresholds()
    print(f"{n} nouveau(x) seuil(s) créé(s) (les seuils déjà présents n'ont pas été modifiés).")
