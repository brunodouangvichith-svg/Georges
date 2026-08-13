"""Teste `engine/confidence.py` — pur, sans DB ni Docker, sur le même
principe que `tests/test_patterns.py`/`tests/test_features.py`."""

from engine.confidence import (
    GEOMETRY_WEIGHT,
    MACD_WEIGHT,
    RSI_WEIGHT,
    STOCH_WEIGHT,
    TREND_WEIGHT,
    VOLUME_WEIGHT,
    confidence_score,
    macd_confirmation,
    stochastic_confirmation,
)
from tests.test_patterns import make_df, ramp


def test_weights_sum_to_one():
    assert GEOMETRY_WEIGHT + VOLUME_WEIGHT + TREND_WEIGHT + RSI_WEIGHT + MACD_WEIGHT + STOCH_WEIGHT == 1.0


def test_confidence_score_is_100_with_all_perfect_subscores_and_no_stochastic():
    """13 détecteurs chartistes classiques (`reversal.py`/`continuation.py`/
    `breakout.py`) : `stoch_conf` n'est jamais calculé, son poids doit être
    intégralement redistribué sur les 5 autres composantes."""
    assert confidence_score(1.0, 1.0, 1.0, 1.0, 1.0) == 100.0


def test_confidence_score_is_100_with_all_perfect_subscores_including_stochastic():
    """Détecteurs de bougies (`candlestick.py`) : `stoch_conf` fourni."""
    assert confidence_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0) == 100.0


def test_confidence_score_is_0_with_all_null_subscores():
    assert confidence_score(0.0, 0.0, 0.0, 0.0, 0.0) == 0.0
    assert confidence_score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0) == 0.0


def test_confidence_score_without_stochastic_ignores_stochastic_weight_entirely():
    """Une figure chartiste classique (`stoch_conf=None`) ne doit jamais être
    docquée pour une dimension hors périmètre — même géométrie/volume/
    tendance/rsi/macd, peu importe qu'une figure bougie obtiendrait un mauvais
    stochastique ou non."""
    without_stoch = confidence_score(0.6, 0.5, 0.5, 0.5, 0.5)
    with_perfect_stoch = confidence_score(0.6, 0.5, 0.5, 0.5, 0.5, 1.0)
    with_null_stoch = confidence_score(0.6, 0.5, 0.5, 0.5, 0.5, 0.0)
    assert with_null_stoch < without_stoch < with_perfect_stoch


def test_macd_confirmation_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert macd_confirmation(df["close"], 5, bullish=True) == 0.5


def test_macd_confirmation_above_zero_on_an_uninterrupted_rally():
    df = make_df(ramp(100, 160, 60))
    at_idx = len(df) - 1
    # Tendance haussière franche et prolongée : la ligne MACD (EMA12-EMA26)
    # est nettement positive -- confirmée pour une figure haussière, pas pour
    # une figure baissière.
    assert macd_confirmation(df["close"], at_idx, bullish=True) == 1.0
    assert macd_confirmation(df["close"], at_idx, bullish=False) == 0.0


def test_stochastic_confirmation_none_before_window_warms_up():
    df = make_df(ramp(100, 110, 10))
    assert stochastic_confirmation(df["high"], df["low"], df["close"], 5, bullish=True) == 0.5


def test_stochastic_confirmation_oversold_confirms_bullish_reversal():
    # Chute continue jusqu'à la dernière séance : %K proche de 0 (clôture au
    # plus bas de la fenêtre) -- confirme une figure haussière (survente),
    # pas une figure baissière (qui attendrait le surachat).
    df = make_df(ramp(120, 100, 30))
    at_idx = len(df) - 1
    assert stochastic_confirmation(df["high"], df["low"], df["close"], at_idx, bullish=True) == 1.0
    assert stochastic_confirmation(df["high"], df["low"], df["close"], at_idx, bullish=False) == 0.0


def test_stochastic_confirmation_overbought_confirms_bearish_reversal():
    df = make_df(ramp(100, 120, 30))
    at_idx = len(df) - 1
    assert stochastic_confirmation(df["high"], df["low"], df["close"], at_idx, bullish=False) == 1.0
    assert stochastic_confirmation(df["high"], df["low"], df["close"], at_idx, bullish=True) == 0.0
