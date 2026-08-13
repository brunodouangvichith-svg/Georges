"""Score de confiance heuristique (0-100) pour une figure détectée.

Combine quatre composantes, chacune normalisée sur [0, 1] :

- **netteté géométrique** (``geometry_quality``) : calculée par chaque
  détecteur (`engine/patterns/*.py`), spécifique à la forme de la figure
  (proximité des niveaux, prominence des extrema, pente des lignes de
  tendance...).
- **confirmation de volume** (`volume_confirmation`) : ratio entre le volume
  du jour clé de la figure (cassure, second creux, etc.) et le volume moyen
  des ``VOLUME_LOOKBACK`` séances précédentes.
- **alignement de tendance** (`trend_alignment`) : position du prix par
  rapport aux moyennes mobiles ``SMA_SHORT``/``SMA_LONG`` (50/200 séances) —
  une figure haussière est plus crédible si la tendance de fond est déjà
  haussière, et inversement pour une figure baissière.
- **confirmation RSI** (`rsi_confirmation`) : ajoutée après lecture de
  *Maîtriser l'analyse technique avec Thami Kabbaj* (voir
  `George_AnalyseTechnique_Kabbaj_Synthese.md` §3.2) — l'auteur y documente un
  cas réel (CAC 40, avril 1997) où une tête-épaules cassée a avorté
  précisément parce que le RSI n'a jamais cassé sa propre zone de neutralité,
  citant explicitement *« les indicateurs techniques priment parfois sur les
  figures graphiques »*. Applique le même filtre uniformément aux 13
  détecteurs déjà existants (pas seulement aux figures de retournement),
  cohérent avec le fait que volume/tendance s'appliquent déjà à tous.
- **confirmation MACD** (`macd_confirmation`) : même principe que le RSI, mais
  sur la ligne du zéro du MACD — la synthèse Kabbaj §4 la présente comme
  *« l'équivalent de la zone de neutralité du RSI pour repérer le sens de la
  tendance »*. Appliquée uniformément aux mêmes détecteurs que le RSI, pour
  la même raison.
- **confirmation stochastique** (`stochastic_confirmation`) : réservée aux
  détecteurs de bougies japonaises (`engine/patterns/candlestick.py`) — le
  livre ne documente le stochastique qu'en combinaison avec elles (§2.7/§4 :
  sortie de zone de surachat/survente + figure de bougie pour confirmer un
  retournement), jamais comme confirmation générale des 13 figures
  chartistes. Voir `confidence_score` ci-dessous pour comment son poids est
  redistribué sur les autres composantes quand elle ne s'applique pas.

Pondération : ``GEOMETRY_WEIGHT`` (0.30) + ``VOLUME_WEIGHT`` (0.15) +
``TREND_WEIGHT`` (0.15) + ``RSI_WEIGHT`` (0.15) + ``MACD_WEIGHT`` (0.15) +
``STOCH_WEIGHT`` (0.10) = 1.0. Rebalancée par rapport aux poids précédents
(0.4/0.2/0.2/0.2) pour faire de la place au MACD et au stochastique tout en
gardant la géométrie comme facteur dominant.
"""

import numpy as np
import pandas as pd

GEOMETRY_WEIGHT = 0.30
VOLUME_WEIGHT = 0.15
TREND_WEIGHT = 0.15
RSI_WEIGHT = 0.15
MACD_WEIGHT = 0.15
STOCH_WEIGHT = 0.10

VOLUME_LOOKBACK = 20
SMA_SHORT = 50
SMA_LONG = 200


def volume_confirmation(volume: pd.Series, at_idx: int, lookback: int = VOLUME_LOOKBACK) -> float:
    """Ratio volume(at_idx) / moyenne(volume des `lookback` séances précédentes),
    saturé sur [0, 1] : un ratio de 0.5x ou moins vaut 0, un ratio de 2x ou
    plus vaut 1, la relation est linéaire entre les deux.

    Repli neutre (0.5) si le volume du jour visé est manquant (`NaN`) — un
    vrai cas rencontré en réingérant en pleine séance (marché encore ouvert,
    même bug de bar incomplète que `close` ailleurs dans le projet, voir
    `api/routers/portfolios.py:_current_price_and_pnl`), qui produisait
    silencieusement une confiance `NaN` en base sans ce garde-fou (attrapé
    en essayant d'insérer une décision dessus : `decimal.InvalidOperation`
    sur une comparaison `<` avec un `Decimal('NaN')`)."""
    if pd.isna(volume.iloc[at_idx]):
        return 0.5
    start = max(0, at_idx - lookback)
    baseline = volume.iloc[start:at_idx]
    if len(baseline) == 0 or baseline.mean() == 0:
        return 0.5
    ratio = volume.iloc[at_idx] / baseline.mean()
    return float(np.clip((ratio - 0.5) / 1.5, 0.0, 1.0))


def trend_alignment(close: pd.Series, bullish: bool) -> float:
    """1.0 si la tendance de fond (SMA50 vs SMA200, prix vs SMA50) soutient
    le sens du pattern, 0.0 si elle s'y oppose totalement, 0.5 si
    l'historique est trop court pour juger."""
    # Import différé, pas au niveau du module : `engine.patterns.common` vit
    # dans le package `engine.patterns`, dont `__init__.py` importe les 25
    # détecteurs — qui importent tous `engine.confidence` (ce module même).
    # Un import en tête de fichier ici créait un cycle réel (pas seulement
    # théorique) : si quoi que ce soit importe `engine.confidence` avant que
    # `engine.patterns` ait déjà été chargé ailleurs (ex. `agents/context.py`
    # important `GEOMETRY_WEIGHT` en tête de fichier), Python tombe sur
    # `ImportError: cannot import name 'confidence_score' from partially
    # initialized module` — `engine.confidence` est encore en cours
    # d'exécution de son propre import de `engine.patterns.common` quand les
    # détecteurs tentent de le réimporter. Repoussé en import différé ici :
    # au moment où `trend_alignment`/`rsi_confirmation` sont réellement
    # appelées, `engine.confidence` est déjà entièrement chargé, donc le
    # cycle ne se referme jamais réellement.
    from engine.patterns.common import sma

    if len(close) < SMA_LONG:
        return 0.5
    sma50 = sma(close, SMA_SHORT).iloc[-1]
    sma200 = sma(close, SMA_LONG).iloc[-1]
    price = close.iloc[-1]
    if pd.isna(sma50) or pd.isna(sma200):
        return 0.5

    above_50 = price > sma50
    trend_up = sma50 > sma200
    score = 0.0
    score += 0.5 if (above_50 == bullish) else 0.0
    score += 0.5 if (trend_up == bullish) else 0.0
    return score


def rsi_confirmation(close: pd.Series, at_idx: int, bullish: bool) -> float:
    """1.0 si le RSI est du bon côté de sa zone de neutralité (`RSI_NEUTRAL_ZONE`,
    50) pour le sens de la figure (au-dessus pour une figure haussière,
    en dessous pour une figure baissière), 0.0 sinon, 0.5 si l'historique est
    insuffisant (`RSI_WINDOW` séances) ou si la valeur est `NaN`."""
    # Import différé — même raison que dans `trend_alignment` ci-dessus.
    from engine.patterns.common import RSI_NEUTRAL_ZONE, rsi

    rsi_series = rsi(close)
    if at_idx >= len(rsi_series):
        return 0.5
    value = rsi_series.iloc[at_idx]
    if pd.isna(value):
        return 0.5
    above_neutral = value > RSI_NEUTRAL_ZONE
    return 1.0 if above_neutral == bullish else 0.0


def macd_confirmation(close: pd.Series, at_idx: int, bullish: bool) -> float:
    """1.0 si la ligne MACD est du bon côté de sa ligne du zéro (au-dessus
    pour une figure haussière, en dessous pour une figure baissière), 0.0
    sinon, 0.5 si l'historique est insuffisant (`MACD_SLOW_SPAN` séances) ou
    si la valeur est `NaN` — même logique que `rsi_confirmation` ci-dessus,
    appliquée à la ligne du zéro du MACD plutôt qu'à la zone de neutralité du
    RSI (`George_AnalyseTechnique_Kabbaj_Synthese.md` §4)."""
    # Import différé — même raison que dans `trend_alignment`/`rsi_confirmation`.
    from engine.patterns.common import macd

    macd_line, _, _ = macd(close)
    if at_idx >= len(macd_line):
        return 0.5
    value = macd_line.iloc[at_idx]
    if pd.isna(value):
        return 0.5
    above_zero = value > 0
    return 1.0 if above_zero == bullish else 0.0


def stochastic_confirmation(high: pd.Series, low: pd.Series, close: pd.Series, at_idx: int, bullish: bool) -> float:
    """1.0 si le %K stochastique est dans la zone qui confirme le sens de la
    figure (survente pour une figure haussière, surachat pour une figure
    baissière), 0.0 sinon, 0.5 si l'historique est insuffisant
    (`STOCHASTIC_WINDOW` séances) ou si la valeur est `NaN`. Réservée aux
    détecteurs de `engine/patterns/candlestick.py` — voir la docstring de
    `confidence_score`."""
    # Import différé — même raison que dans `trend_alignment`/`rsi_confirmation`.
    from engine.patterns.common import STOCHASTIC_OVERBOUGHT, STOCHASTIC_OVERSOLD, stochastic_oscillator

    percent_k, _ = stochastic_oscillator(high, low, close)
    if at_idx >= len(percent_k):
        return 0.5
    value = percent_k.iloc[at_idx]
    if pd.isna(value):
        return 0.5
    if bullish:
        return 1.0 if value < STOCHASTIC_OVERSOLD else 0.0
    return 1.0 if value > STOCHASTIC_OVERBOUGHT else 0.0


def confidence_score(
    geometry_quality: float,
    volume_conf: float,
    trend_conf: float,
    rsi_conf: float,
    macd_conf: float,
    stoch_conf: float | None = None,
) -> float:
    """Combine les composantes en un score final 0-100 (1 décimale).

    `stoch_conf` est optionnel : seuls les détecteurs de bougies japonaises
    (`engine/patterns/candlestick.py`) le calculent (voir sa docstring
    ci-dessus). Quand il est absent, son poids (`STOCH_WEIGHT`) est
    redistribué proportionnellement sur les 5 autres composantes plutôt que
    de pénaliser silencieusement une figure pour une dimension qui ne
    s'applique pas à elle — même philosophie que `engine/george_index.py`
    (`None` plutôt qu'un 0 pour un cas hors périmètre)."""
    if stoch_conf is None:
        scale = 1.0 / (1.0 - STOCH_WEIGHT)
        raw = scale * (
            GEOMETRY_WEIGHT * geometry_quality
            + VOLUME_WEIGHT * volume_conf
            + TREND_WEIGHT * trend_conf
            + RSI_WEIGHT * rsi_conf
            + MACD_WEIGHT * macd_conf
        )
    else:
        raw = (
            GEOMETRY_WEIGHT * geometry_quality
            + VOLUME_WEIGHT * volume_conf
            + TREND_WEIGHT * trend_conf
            + RSI_WEIGHT * rsi_conf
            + MACD_WEIGHT * macd_conf
            + STOCH_WEIGHT * stoch_conf
        )
    return round(float(np.clip(raw, 0.0, 1.0)) * 100, 1)
