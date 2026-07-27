import pandas as pd
import pytest

from engine.exit_scenarios import classify_exit


def test_take_profit_is_always_sortie_totale_with_no_volume_check():
    volume = pd.Series([1_000_000] * 25)
    scenario, volume_confirmed = classify_exit("take_profit_hit", volume, hit_idx=20)
    assert scenario == "sortie_totale"
    assert volume_confirmed is None


def test_stop_loss_with_high_volume_is_sortie_totale():
    volume = pd.Series([1_000_000] * 20 + [2_500_000])  # 2.5x la moyenne des 20 séances précédentes
    scenario, volume_confirmed = classify_exit("stop_loss_hit", volume, hit_idx=20)
    assert scenario == "sortie_totale"
    assert volume_confirmed is True


def test_stop_loss_with_low_volume_is_sortie_partielle():
    volume = pd.Series([1_000_000] * 20 + [900_000])  # sous la moyenne : pas de confirmation
    scenario, volume_confirmed = classify_exit("stop_loss_hit", volume, hit_idx=20)
    assert scenario == "sortie_partielle"
    assert volume_confirmed is False


def test_unhandled_result_raises():
    with pytest.raises(ValueError):
        classify_exit("open", pd.Series([1_000_000] * 10), hit_idx=5)
