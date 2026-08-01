"""Score du panier Carry Trade — implémentation (ad hoc, pas une phase du
roadmap). Mêmes conventions que `engine/george_index.py` : module sans
accès DB, travaille sur des structures déjà chargées, pour rester testable
sur des données synthétiques (voir `tests/test_carry_index.py`). Le
chargement depuis la base est fait par `engine/compute_carry_index.py`.

**Différence volontaire avec le George Index** : pas de score composite de
panier (pas de `compute_carry_basket_index` agrégé) — le prototype fourni
par l'utilisateur note chaque paire individuellement, sans indice composite
du panier entier ; ajouter un tel agrégat serait une fonctionnalité non
demandée.

**La décision Achat/Surveiller/Alléger est une heuristique simple sur le
score de saturation, pas un modèle appris/backtesté** (contrairement au
score de confiance des actions, `engine/scoring.py`) — les seuils
reprennent ceux du prototype fourni, à ajuster si l'usage réel le suggère."""

from __future__ import annotations

import numpy as np
import pandas as pd

REALIZED_VOL_WINDOW_SESSIONS = 20
TRADING_SESSIONS_PER_YEAR = 252

CROWDING_ALLEGER_THRESHOLD = 75.0
CROWDING_SURVEILLER_THRESHOLD = 60.0


def realized_volatility(df: pd.DataFrame, window: int = REALIZED_VOL_WINDOW_SESSIONS) -> float | None:
    """Volatilité réalisée annualisée (%) sur les `window` derniers
    rendements log quotidiens de `df['close']`. `None` si l'historique est
    insuffisant (moins de `window + 1` séances)."""
    if len(df) <= window:
        return None
    closes = df["close"].iloc[-(window + 1) :]
    log_returns = np.log(closes / closes.shift(1)).dropna()
    if log_returns.empty:
        return None
    return float(log_returns.std() * np.sqrt(TRADING_SESSIONS_PER_YEAR) * 100)


def carry_differential(target_rate_pct: float, funding_rate_pct: float) -> float:
    """Différentiel de taux simple (pas de composition) entre la devise
    cible et la devise de financement — même approximation que le
    prototype fourni."""
    return float(target_rate_pct - funding_rate_pct)


def cot_crowding_score(lev_money_long: int, lev_money_short: int, open_interest_all: int) -> float | None:
    """Score de saturation 0-100 à partir du positionnement "Leveraged
    Funds" du rapport CFTC TFF sur la devise de financement : écart
    long/short en proportion de l'open interest total, plus l'écart est
    grand (dans un sens ou l'autre), plus la position est jugée surpeuplée.
    `None` si `open_interest_all` est nul (donnée non exploitable)."""
    if open_interest_all == 0:
        return None
    return float(np.clip(abs(lev_money_long - lev_money_short) / open_interest_all * 100, 0, 100))


def decide_for_crowding(crowding_score: float | None) -> str:
    """Heuristique simple (pas un modèle appris) : reprend les seuils du
    prototype fourni. Un score de saturation inconnu (`None`) est traité
    comme non préoccupant plutôt que de bloquer l'affichage d'une décision —
    cohérent avec le reste du projet qui préfère un repli neutre à une
    valeur fabriquée."""
    if crowding_score is None:
        return "Achat"
    if crowding_score >= CROWDING_ALLEGER_THRESHOLD:
        return "Alléger"
    if crowding_score >= CROWDING_SURVEILLER_THRESHOLD:
        return "Surveiller"
    return "Achat"


def compute_carry_score(
    funding_rate_pct: float | None,
    target_rate_pct: float | None,
    fx_prices: pd.DataFrame | None,
    cot: dict | None,
) -> dict:
    """Assemble le score complet d'une paire à partir de ses données déjà
    chargées. Chaque champ reste `None` s'il n'est pas calculable plutôt
    que fabriqué — même discipline que `engine/george_index.py`.

    `cot` : `{"lev_money_long", "lev_money_short", "open_interest_all"}` ou
    `None` si aucune donnée COT n'est disponible pour la devise de
    financement de cette paire."""
    carry_pct = (
        carry_differential(target_rate_pct, funding_rate_pct)
        if funding_rate_pct is not None and target_rate_pct is not None
        else None
    )
    vol_pct = realized_volatility(fx_prices) if fx_prices is not None and not fx_prices.empty else None
    ratio = (carry_pct / vol_pct) if carry_pct is not None and vol_pct not in (None, 0) else None
    crowding = (
        cot_crowding_score(cot["lev_money_long"], cot["lev_money_short"], cot["open_interest_all"])
        if cot is not None
        else None
    )
    return {
        "carry_pct": round(carry_pct, 2) if carry_pct is not None else None,
        "realized_vol_pct": round(vol_pct, 2) if vol_pct is not None else None,
        "carry_vol_ratio": round(ratio, 2) if ratio is not None else None,
        "cot_crowding_score": round(crowding, 1) if crowding is not None else None,
        "decision": decide_for_crowding(crowding),
    }
