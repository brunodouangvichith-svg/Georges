"""Backtesting des figures détectées : calcule le rendement réel après 5, 10
et 20 séances, et assemble une ligne d'entraînement (features + labels) pour
le modèle de confiance appris (Phase 2).

Module volontairement sans accès DB — il ne travaille que sur des
DataFrames OHLCV déjà chargés, pour rester testable sur des séries
synthétiques (voir tests/test_backtest.py). Le chargement depuis
PostgreSQL et l'assemblage du jeu de données complet sont faits
par `engine/build_training_set.py` (script), pas ici.

Paramètres :
- ``HORIZONS`` (5, 10, 20 séances) : horizons de calcul du rendement futur.
- ``SUCCESS_THRESHOLD`` (0.0) : rendement (%) au-delà duquel une figure
  haussière est considérée un succès (une figure baissière est un succès si
  le rendement est en dessous de `-SUCCESS_THRESHOLD`). Seuil volontairement
  simple (juste positif/négatif) plutôt qu'un objectif de rendement précis :
  les niveaux de take-profit/stop-loss réels ne sont fixés qu'au moment de
  la Décision (Phase 3+), pas au moment de la détection du pattern.
- ``TRAINING_HORIZON`` (10 séances) : horizon retenu comme cible principale
  d'entraînement du modèle (voir `engine/notebooks/train_confidence_model.ipynb`) ;
  les autres horizons restent calculés pour l'analyse.
"""

import pandas as pd

from engine.features import atr_pct, position_vs_moving_averages, relative_volume

HORIZONS = (5, 10, 20)
TRAINING_HORIZON = 10
SUCCESS_THRESHOLD = 0.0

BEARISH_PATTERNS = {
    "Double Top",
    "Head & Shoulders",
    "Descending Triangle",
    "Rising Wedge",
    "Bear Flag",
    "Breakdown",
}


def is_bullish(pattern_type: str) -> bool:
    return pattern_type not in BEARISH_PATTERNS


def forward_returns(df: pd.DataFrame, at_idx: int, horizons=HORIZONS) -> dict[int, float]:
    """Rendement (%) entre la clôture à `at_idx` et la clôture `h` séances
    plus tard, pour chaque horizon dont la série va assez loin."""
    base = df["close"].iloc[at_idx]
    out = {}
    for h in horizons:
        target_idx = at_idx + h
        if target_idx >= len(df):
            continue
        out[h] = float((df["close"].iloc[target_idx] - base) / base * 100)
    return out


def label_success(return_pct: float, pattern_type: str, threshold: float = SUCCESS_THRESHOLD) -> bool:
    return return_pct > threshold if is_bullish(pattern_type) else return_pct < -threshold


def compute_market_trend(price_frames: dict[str, pd.DataFrame], at_date, lookback: int = 20) -> float | None:
    """Rendement moyen (%) de l'univers sur les `lookback` séances précédant
    `at_date` — proxy de la tendance de marché en l'absence d'un indice de
    référence dédié dans le schéma actuel (même limitation documentée dans
    `engine/george_index.md`)."""
    returns = []
    for df in price_frames.values():
        sub = df[df.index <= at_date]
        if len(sub) < lookback + 1:
            continue
        base = sub["close"].iloc[-1 - lookback]
        if base == 0:
            continue
        returns.append(float((sub["close"].iloc[-1] - base) / base * 100))
    if not returns:
        return None
    return sum(returns) / len(returns)


def build_sample(
    df: pd.DataFrame,
    at_idx: int,
    pattern_type: str,
    sector: str,
    market_trend: float | None,
    horizons=HORIZONS,
) -> dict | None:
    """Construit une ligne d'entraînement (features + labels) pour une
    figure détectée à `at_idx`. `None` si la série ne va pas assez loin
    après `at_idx` pour juger le résultat au plus long des horizons demandés."""
    returns = forward_returns(df, at_idx, horizons=horizons)
    if max(horizons) not in returns:
        return None

    ma_features = position_vs_moving_averages(df, at_idx) or {
        "price_over_sma50": None,
        "price_over_sma200": None,
        "sma50_over_sma200": None,
    }
    sample = {
        "pattern_type": pattern_type,
        "sector": sector,
        "relative_volume": relative_volume(df, at_idx),
        "atr_pct": atr_pct(df, at_idx),
        "market_trend": market_trend,
        **ma_features,
    }
    for h, ret in returns.items():
        sample[f"return_{h}"] = ret
        sample[f"success_{h}"] = label_success(ret, pattern_type)
    return sample


def build_training_set(samples: list[dict]) -> pd.DataFrame:
    """Assemble une liste de `build_sample(...)` (en ignorant les `None`) en
    un DataFrame prêt pour l'entraînement."""
    rows = [s for s in samples if s is not None]
    return pd.DataFrame(rows)
