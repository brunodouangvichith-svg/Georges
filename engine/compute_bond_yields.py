"""Lecture/agrégation DB pour Obligataire Watch (ad hoc, pas une phase du
roadmap) — le pendant DB-touching de `engine/bond_spread.py` (pur). Consommé
par `api/routers/bonds.py` et `engine/bond_bulletin.py`.

**Choix de l'observation de comparaison pour les variations 24h/7j/30j** :
OAT/Bund (séries OCDE mensuelles) n'ont physiquement pas de point à "24h"
d'écart — leur variation 24h est donc toujours `None`, jamais une valeur
recalculée sur la même observation. `WINDOW_TOLERANCE_DAYS` fixe, par
fenêtre demandée, l'écart maximal toléré pour accepter une observation
passée comme "la" comparaison pertinente — conforme à la consigne explicite
du cahier des charges : "ne comparer deux observations que si leur contexte
temporel est pertinent"."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.bond_spread import curve_slope_bps, spread_bps, variation_bps
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_UST_US_10Y,
    BOND_INSTRUMENT_UST_US_2Y,
    BondYieldSnapshot,
)

TRACKED_INSTRUMENTS = [
    BOND_INSTRUMENT_OAT_FR_10Y,
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_UST_US_10Y,
    BOND_INSTRUMENT_UST_US_2Y,
]

# (étiquette affichée, fenêtre en jours, tolérance en jours pour accepter
# une observation comme "la" comparaison de cette fenêtre).
VARIATION_WINDOWS = [("24h", 1, 1), ("7j", 7, 3), ("30j", 30, 10)]


def load_latest_snapshot(db: Session, instrument: str) -> BondYieldSnapshot | None:
    stmt = (
        select(BondYieldSnapshot)
        .where(BondYieldSnapshot.instrument == instrument)
        .order_by(BondYieldSnapshot.observed_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def load_history(db: Session, instrument: str, limit: int = 365) -> list[BondYieldSnapshot]:
    """Historique chronologique croissant (le plus ancien en premier — pour
    un tracé de graphique direct), le plus récent `limit` observations."""
    stmt = (
        select(BondYieldSnapshot)
        .where(BondYieldSnapshot.instrument == instrument)
        .order_by(BondYieldSnapshot.observed_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return list(reversed(rows))


def _load_history_window(db: Session, instrument: str, before: datetime.date, since: datetime.date) -> list[BondYieldSnapshot]:
    """Historique borné par date (pas par nombre de lignes) — utilisé par
    `compute_variations`, qui n'a besoin que des quelques observations
    tombant dans la tolérance de chaque fenêtre, jamais de tout l'historique
    de l'instrument. Filtré en SQL plutôt qu'en Python après un `load_history`
    à limite fixe, qui lirait jusqu'à `limit` lignes à chaque appel sur
    `GET /bonds` (4 instruments) même quand seules 2-3 lignes proches de
    `since` comptent réellement."""
    stmt = (
        select(BondYieldSnapshot)
        .where(
            BondYieldSnapshot.instrument == instrument,
            BondYieldSnapshot.observed_at < before,
            BondYieldSnapshot.observed_at >= since,
        )
        .order_by(BondYieldSnapshot.observed_at)
    )
    return db.execute(stmt).scalars().all()


def _nearest_snapshot(
    snapshots: list[BondYieldSnapshot], target_date: datetime.date, tolerance_days: int
) -> BondYieldSnapshot | None:
    candidates = [s for s in snapshots if abs((s.observed_at - target_date).days) <= tolerance_days]
    if not candidates:
        return None
    return min(candidates, key=lambda s: abs((s.observed_at - target_date).days))


def _values_if_contemporaneous(
    a: BondYieldSnapshot | None, b: BondYieldSnapshot | None, tolerance_days: int
) -> tuple[float, float] | tuple[None, None]:
    """Renvoie `(a.value_pct, b.value_pct)` seulement si leurs `observed_at`
    tombent dans `tolerance_days` l'un de l'autre, sinon `(None, None)` —
    même discipline que `compute_variations` (ne jamais comparer deux
    observations dont le contexte temporel n'est pas pertinent), appliquée
    ici au spread OAT-Bund et à la pente US plutôt qu'aux seules variations
    24h/7j/30j. Un instrument manquant des deux côtés renvoie aussi
    `(None, None)`."""
    if a is None or b is None:
        return None, None
    if abs((a.observed_at - b.observed_at).days) > tolerance_days:
        return None, None
    return float(a.value_pct), float(b.value_pct)


# OAT/Bund (OCDE, mensuel) : deux publications du même mois calendaire sont
# considérées comparables, jusqu'à ~45 jours d'écart au pire si l'une des deux
# séries a du retard. UST10/UST2 (FRED, quotidien) : tolérance resserrée à 5
# jours, largement suffisant pour deux séries quotidiennes réellement à jour.
SPREAD_CONTEMPORANEOUS_TOLERANCE_DAYS = 45
US_CURVE_CONTEMPORANEOUS_TOLERANCE_DAYS = 5


def compute_variations(db: Session, instrument: str, latest: BondYieldSnapshot) -> dict[str, float | None]:
    """Variation en points de base pour chaque fenêtre de `VARIATION_WINDOWS`,
    `None` quand aucune observation passée ne tombe dans la tolérance de
    cette fenêtre (ex. toujours `None` pour "24h" sur une série mensuelle)."""
    max_lookback_days = max(window_days + tolerance_days for _label, window_days, tolerance_days in VARIATION_WINDOWS)
    history = _load_history_window(
        db,
        instrument,
        before=latest.observed_at,
        since=latest.observed_at - datetime.timedelta(days=max_lookback_days),
    )
    variations: dict[str, float | None] = {}
    for label, window_days, tolerance_days in VARIATION_WINDOWS:
        target = latest.observed_at - datetime.timedelta(days=window_days)
        comparison = _nearest_snapshot(history, target, tolerance_days)
        variations[label] = (
            variation_bps(float(latest.value_pct), float(comparison.value_pct)) if comparison is not None else None
        )
    return variations


def build_dashboard_summary(db: Session) -> dict:
    """Assemble les cartes de synthèse + spread OAT-Bund + pente US —
    consommé directement par `GET /bonds` (`api/routers/bonds.py`). Un
    instrument jamais collecté a toutes ses valeurs à `None` plutôt que
    d'être omis — le tableau de bord doit pouvoir afficher "donnée
    indisponible" explicitement (cahier des charges §9)."""
    latest_by_instrument: dict[str, BondYieldSnapshot | None] = {
        instrument: load_latest_snapshot(db, instrument) for instrument in TRACKED_INSTRUMENTS
    }

    cards = []
    for instrument in TRACKED_INSTRUMENTS:
        latest = latest_by_instrument[instrument]
        if latest is None:
            cards.append(
                {
                    "instrument": instrument,
                    "value_pct": None,
                    "observed_at": None,
                    "fetched_at": None,
                    "source_name": None,
                    "source_url": None,
                    "variations_bps": {label: None for label, *_ in VARIATION_WINDOWS},
                }
            )
            continue
        cards.append(
            {
                "instrument": instrument,
                "value_pct": float(latest.value_pct),
                "observed_at": latest.observed_at.isoformat(),
                "fetched_at": latest.fetched_at.isoformat(),
                "source_name": latest.source_name,
                "source_url": latest.source_url,
                "variations_bps": compute_variations(db, instrument, latest),
            }
        )

    oat = latest_by_instrument[BOND_INSTRUMENT_OAT_FR_10Y]
    bund = latest_by_instrument[BOND_INSTRUMENT_BUND_DE_10Y]
    ust10 = latest_by_instrument[BOND_INSTRUMENT_UST_US_10Y]
    ust2 = latest_by_instrument[BOND_INSTRUMENT_UST_US_2Y]

    oat_value, bund_value = _values_if_contemporaneous(oat, bund, SPREAD_CONTEMPORANEOUS_TOLERANCE_DAYS)
    ust10_value, ust2_value = _values_if_contemporaneous(ust10, ust2, US_CURVE_CONTEMPORANEOUS_TOLERANCE_DAYS)

    return {
        "cards": cards,
        "spread_oat_bund_bps": spread_bps(oat_value, bund_value),
        "us_curve_slope_bps": curve_slope_bps(ust10_value, ust2_value),
    }
