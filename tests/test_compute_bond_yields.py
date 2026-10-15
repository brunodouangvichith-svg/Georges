"""Tests de `engine/compute_bond_yields.py:_nearest_snapshot` -- pur, aucune
DB (instances `BondYieldSnapshot` construites directement en mémoire, même
principe que `tests/test_agents.py` pour `Decision`/`Security`). Couvre la
consigne du cahier des charges : "ne comparer deux observations que si leur
contexte temporel est pertinent" -- une observation hors tolérance ne doit
jamais être choisie comme point de comparaison."""

import datetime

from engine.compute_bond_yields import _nearest_snapshot, _values_if_contemporaneous
from ingestion.models import BondYieldSnapshot


def _snapshot(observed_at: datetime.date, value_pct: float = 1.0) -> BondYieldSnapshot:
    return BondYieldSnapshot(
        instrument="UST_US_10Y", value_pct=value_pct, observed_at=observed_at, source_name="FRED", source_url=None
    )


def test_nearest_snapshot_picks_the_closest_within_tolerance():
    snapshots = [_snapshot(datetime.date(2026, 10, 1)), _snapshot(datetime.date(2026, 10, 5)), _snapshot(datetime.date(2026, 10, 10))]
    target = datetime.date(2026, 10, 6)
    nearest = _nearest_snapshot(snapshots, target, tolerance_days=3)
    assert nearest.observed_at == datetime.date(2026, 10, 5)


def test_nearest_snapshot_returns_none_when_nothing_within_tolerance():
    # Série mensuelle (un seul point, loin de la fenêtre "24h") -- doit
    # renvoyer None plutôt qu'une comparaison non pertinente.
    snapshots = [_snapshot(datetime.date(2026, 9, 1))]
    target = datetime.date(2026, 10, 14)  # ~43 jours d'écart
    assert _nearest_snapshot(snapshots, target, tolerance_days=1) is None


def test_nearest_snapshot_returns_none_for_empty_history():
    assert _nearest_snapshot([], datetime.date(2026, 10, 1), tolerance_days=10) is None


def test_nearest_snapshot_exact_match_wins_over_a_further_candidate():
    snapshots = [_snapshot(datetime.date(2026, 10, 3)), _snapshot(datetime.date(2026, 10, 7))]
    target = datetime.date(2026, 10, 7)
    nearest = _nearest_snapshot(snapshots, target, tolerance_days=10)
    assert nearest.observed_at == datetime.date(2026, 10, 7)


def test_values_if_contemporaneous_returns_both_values_within_tolerance():
    a = _snapshot(datetime.date(2026, 10, 1), value_pct=4.00)
    b = _snapshot(datetime.date(2026, 10, 3), value_pct=2.80)
    assert _values_if_contemporaneous(a, b, tolerance_days=5) == (4.00, 2.80)


def test_values_if_contemporaneous_returns_none_pair_when_dates_are_incompatible():
    # Cahier des charges : "ne comparer deux observations que si leur
    # contexte temporel est pertinent" -- un OAT d'août comparé à un Bund de
    # janvier ne doit jamais produire un spread.
    a = _snapshot(datetime.date(2026, 8, 1), value_pct=4.00)
    b = _snapshot(datetime.date(2026, 1, 1), value_pct=2.80)
    assert _values_if_contemporaneous(a, b, tolerance_days=45) == (None, None)


def test_values_if_contemporaneous_returns_none_pair_when_either_side_is_missing():
    a = _snapshot(datetime.date(2026, 10, 1), value_pct=4.00)
    assert _values_if_contemporaneous(a, None, tolerance_days=45) == (None, None)
    assert _values_if_contemporaneous(None, a, tolerance_days=45) == (None, None)
    assert _values_if_contemporaneous(None, None, tolerance_days=45) == (None, None)


def test_values_if_contemporaneous_boundary_is_inclusive():
    a = _snapshot(datetime.date(2026, 10, 1), value_pct=4.00)
    b = _snapshot(datetime.date(2026, 10, 6), value_pct=2.80)  # exactement 5 jours d'écart
    assert _values_if_contemporaneous(a, b, tolerance_days=5) == (4.00, 2.80)
    assert _values_if_contemporaneous(a, b, tolerance_days=4) == (None, None)
