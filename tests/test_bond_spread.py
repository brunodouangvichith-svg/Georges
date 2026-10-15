"""Tests de `engine/bond_spread.py` -- pur, aucune DB/réseau. Les 3 cas
chiffrés viennent directement des exemples du cahier des charges Obligataire
Watch §13, repris tels quels comme cas de test de référence."""

from engine.bond_spread import curve_slope_bps, spread_bps, variation_bps


def test_spread_bps_cahier_des_charges_example():
    # OAT = 4,00 % ; Bund = 2,80 % -> spread = 120 points de base.
    assert spread_bps(4.00, 2.80) == 120.0


def test_curve_slope_bps_cahier_des_charges_example():
    # Treasury 10 ans = 4,50 % ; Treasury 2 ans = 4,00 % -> pente = 50 points de base.
    assert curve_slope_bps(4.50, 4.00) == 50.0


def test_variation_bps_cahier_des_charges_example():
    # Rendement précédent = 3,50 % ; rendement actuel = 3,60 % -> variation = +10 points de base.
    assert variation_bps(3.60, 3.50) == 10.0


def test_spread_bps_never_confuses_percent_and_basis_points():
    # Un écart de 0,10 point de pourcentage (ex. 3,50 % -> 3,60 %) doit
    # toujours ressortir en 10 pb, jamais en 0,10 (le point de pourcentage
    # brut, non multiplié par 100).
    assert variation_bps(3.60, 3.50) == 10.0
    assert variation_bps(3.60, 3.50) != 0.10


def test_spread_bps_handles_negative_spread():
    assert spread_bps(2.80, 4.00) == -120.0


def test_spread_bps_none_when_instrument_a_missing():
    assert spread_bps(None, 2.80) is None


def test_spread_bps_none_when_instrument_b_missing():
    assert spread_bps(4.00, None) is None


def test_curve_slope_bps_negative_signals_inverted_curve():
    assert curve_slope_bps(3.80, 4.20) == -40.0


def test_curve_slope_bps_none_when_either_value_missing():
    assert curve_slope_bps(None, 4.00) is None
    assert curve_slope_bps(4.50, None) is None


def test_variation_bps_none_when_either_value_missing():
    assert variation_bps(None, 3.50) is None
    assert variation_bps(3.60, None) is None


def test_variation_bps_zero_when_unchanged():
    assert variation_bps(3.50, 3.50) == 0.0
