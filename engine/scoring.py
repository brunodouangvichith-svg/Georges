"""Inférence en production du score de confiance (Phase 2).

Charge le modèle appris le plus récent (entraîné offline par
`engine/notebooks/train_confidence_model.ipynb`, sauvegardé par
`joblib` sous `engine/models/confidence_xgb_<date>.joblib` +
`confidence_xgb_<date>.meta.json`) et prédit une probabilité de succès,
convertie en score 0-100.

**Retombe sur le score heuristique de la Phase 1** (`match.confidence`,
déjà calculé par le détecteur — voir `engine/confidence.py`) dans tous les
cas où le score appris n'est pas fiable ou indisponible :
- aucun modèle entraîné trouvé sur disque,
- historique de prix insuffisant pour ce titre (moins de 200 séances : pas
  de SMA200 fiable) ou volume/ATR non calculables,
- toute erreur d'inférence inattendue.

Jamais d'exception ne remonte au code appelant : au pire, on récupère la
confiance heuristique déjà calculée.
"""

import glob
import json
import math
import os

import joblib
import pandas as pd

from engine.backtest import compute_market_trend
from engine.features import (
    atr_pct,
    bb_percent_b,
    macd_hist_pct,
    position_vs_moving_averages,
    relative_volume,
    rsi_at,
    stochastic_k_at,
)
from engine.patterns.common import PatternMatch

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_GLOB = os.path.join(MODELS_DIR, "confidence_xgb_*.joblib")

_cache_loaded = False
_cached_model = None
_cached_feature_columns: list[str] | None = None


def latest_model_path() -> str | None:
    candidates = sorted(glob.glob(MODEL_GLOB))
    return candidates[-1] if candidates else None


def load_latest_model():
    """Charge (et met en cache pour le process) le modèle le plus récent.
    Renvoie `(None, None)` si aucun modèle n'est disponible ou ne peut être
    chargé — ne lève jamais d'exception."""
    global _cache_loaded, _cached_model, _cached_feature_columns
    if _cache_loaded:
        return _cached_model, _cached_feature_columns
    _cache_loaded = True

    path = latest_model_path()
    if path is None:
        return None, None

    meta_path = path.removesuffix(".joblib") + ".meta.json"
    try:
        model = joblib.load(path)
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        _cached_model = model
        _cached_feature_columns = meta["feature_columns"]
    except Exception:
        _cached_model, _cached_feature_columns = None, None
    return _cached_model, _cached_feature_columns


def reset_model_cache() -> None:
    """Force le rechargement au prochain appel (utile après un nouvel
    entraînement, ou dans les tests)."""
    global _cache_loaded, _cached_model, _cached_feature_columns
    _cache_loaded = False
    _cached_model = None
    _cached_feature_columns = None


def build_feature_row(
    df: pd.DataFrame,
    at_idx: int,
    pattern_type: str,
    sector: str,
    price_frames: dict[str, pd.DataFrame] | None = None,
    at_date=None,
) -> dict | None:
    """Construit la ligne de features pour une détection au bar `at_idx` de
    `df`. Renvoie `None` si l'historique de ce titre est insuffisant pour
    des features fiables (volume relatif, ATR ou position vs moyennes
    mobiles indisponibles) — c'est ce signal que `predict_confidence`
    utilise pour retomber sur l'heuristique. `market_trend` (contexte de
    marché), `rsi_14`, `macd_hist_pct`, `bb_percent_b` et `stochastic_k` sont
    en revanche optionnels : leur absence ne bloque pas l'inférence, ils
    seront simplement imputés par le pipeline entraîné (aucun ne nécessite
    plus qu'une fenêtre de quelques dizaines de séances au maximum, nettement
    moins que la SMA200 déjà gatante ci-dessus — pas de raison de les faire
    bloquer aussi)."""
    ma_features = position_vs_moving_averages(df, at_idx)
    rel_vol = relative_volume(df, at_idx)
    atr = atr_pct(df, at_idx)
    if ma_features is None or rel_vol is None or atr is None:
        return None

    market_trend = compute_market_trend(price_frames, at_date) if price_frames and at_date is not None else None
    rsi_value = rsi_at(df, at_idx)
    macd_value = macd_hist_pct(df, at_idx)
    bb_value = bb_percent_b(df, at_idx)
    stoch_value = stochastic_k_at(df, at_idx)

    return {
        "pattern_type": pattern_type,
        "sector": sector,
        "relative_volume": rel_vol,
        "atr_pct": atr,
        "market_trend": market_trend if market_trend is not None else math.nan,
        "rsi_14": rsi_value if rsi_value is not None else math.nan,
        "macd_hist_pct": macd_value if macd_value is not None else math.nan,
        "bb_percent_b": bb_value if bb_value is not None else math.nan,
        "stochastic_k": stoch_value if stoch_value is not None else math.nan,
        **ma_features,
    }


def predict_confidence(
    match: PatternMatch,
    df: pd.DataFrame,
    sector: str,
    price_frames: dict[str, pd.DataFrame] | None = None,
) -> tuple[float, str]:
    """Score 0-100 pour `match` (probabilité prédite par le modèle appris si
    possible, sinon `match.confidence`, l'heuristique de la Phase 1) et la
    source de ce score (`"modele_appris"` ou `"heuristique"`) — cette
    deuxième valeur est stockée dans `patterns_detected.context` par
    `engine.run_detection.run` et forwardée jusqu'à l'explication LLM
    (`agents/context.py`), pour que George ne prétende jamais que le score
    final est la somme pondérée des 4 sous-scores de `engine.confidence`
    quand il vient en réalité du modèle appris (les deux peuvent diverger
    fortement — un modèle entraîné sur l'historique complet peut corriger
    l'heuristique, pas seulement la confirmer)."""
    model, feature_columns = load_latest_model()
    if model is None:
        return match.confidence, "heuristique"

    at_idx = len(df) - 1  # les détecteurs ne confirment qu'au dernier bar disponible
    features = build_feature_row(df, at_idx, match.pattern_type, sector, price_frames, match.detected_at)
    if features is None:
        return match.confidence, "heuristique"

    try:
        row = pd.DataFrame([features])[feature_columns]
        proba = model.predict_proba(row)[0, 1]
    except Exception:
        return match.confidence, "heuristique"
    return round(float(proba) * 100, 1), "modele_appris"
