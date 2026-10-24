"""`engine/strategic_risk.py` — pur."""

import pytest

from engine.strategic_risk import bond_risk_level


@pytest.mark.parametrize(
    ("oat", "spread", "expected"),
    [
        (5.1, 155.0, "rouge"),
        (5.1, 140.0, "orange"),  # une seule des deux conditions rouges
        (4.9, 160.0, "orange"),
        (4.4, 110.0, "vert"),
        (4.6, 110.0, "orange"),  # spread bas mais OAT encore haute
        (4.48, 101.0, "vert"),
        (None, 120.0, "indetermine"),
        (4.5, None, "indetermine"),
    ],
)
def test_bond_risk_level(oat, spread, expected):
    assert bond_risk_level(oat, spread) == expected
