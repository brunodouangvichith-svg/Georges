"""Mesures de liquidité et de risque par valeur, pour la fiche « Valeur
sélectionnée » de l'écran Univers : volume quotidien moyen, volatilité
réalisée, ATR, bêta et corrélation avec le CAC 40, corrélation avec le
secteur. Calcul pur (aucun accès base ni réseau).

Conventions :
- Rendements logarithmiques de clôture à clôture, sur les cours stockés :
  ajustés des divisions par Yahoo, **pas** des dividendes (comme l'indice
  CAC 40, qui est un indice de prix).
- La séance datée d'aujourd'hui (heure de Paris) est écartée : téléchargée en
  cours de journée, son volume et son amplitude sont partiels.
- ``None`` quand l'historique est insuffisant, jamais 0.
- Bêta et corrélation CAC 40 : les clôtures de la valeur et de l'indice sont
  d'abord alignées sur leurs séances communes, puis les rendements calculés,
  pour que chaque paire couvre le même intervalle.
- « Secteur » = la famille avant `` / `` (comme sur le tore) ; la référence est
  la moyenne équipondérée des rendements des **autres** valeurs suivies de
  cette famille.
"""

import numpy as np
import pandas as pd

from engine.features import ATR_WINDOW, average_true_range

ADV_WINDOW = 20
RETURN_WINDOW = 252  # séances : un an
TRADING_DAYS_PER_YEAR = 252
# Au-delà, 252 séances communes ne représentent plus « un an » (série trouée).
MAX_WINDOW_DAYS = 400
# Corrélation sectorielle : séances sur 252 où la valeur et au moins
# MIN_PEERS autres valeurs du secteur ont un rendement.
MIN_SECTOR_OBSERVATIONS = 227  # 90 % de 252
MIN_PEERS = 2
# Variation en une séance signalée comme à vérifier (opération sur titres mal
# ajustée par la source, ou vrai choc) : la mesure reste affichée.
JUMP_THRESHOLD = 0.5
PARIS = "Europe/Paris"


def session_index(index) -> pd.DatetimeIndex:
    """Date de séance à l'heure de Paris. La base renvoie minuit Paris en UTC
    (22 h/23 h la veille) : sans conversion, la séance changerait de jour."""
    dates = pd.DatetimeIndex(pd.to_datetime(index, utc=True))
    return dates.tz_convert(PARIS).tz_localize(None).normalize()


def completed_sessions(df: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    """`df` réindexé par date de séance, sans la séance en cours ni les
    clôtures inexploitables."""
    out = df.copy()
    out.index = session_index(df.index)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out[(out.index < today) & np.isfinite(out["close"]) & (out["close"] > 0)]


def _finite(value) -> float | None:
    return float(value) if value is not None and np.isfinite(value) else None


def _log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff().iloc[1:]


def _last_year(returns):
    """Les 252 dernières observations, ou `None` si elles manquent ou
    s'étalent sur bien plus d'un an."""
    if len(returns) < RETURN_WINDOW:
        return None
    window = returns.iloc[-RETURN_WINDOW:]
    if (window.index[-1] - window.index[0]).days > MAX_WINDOW_DAYS:
        return None
    return window


def _correlation(a: pd.Series, b: pd.Series) -> float | None:
    if a.std() == 0 or b.std() == 0:
        return None
    return _finite(a.corr(b))


def _own_metrics(df: pd.DataFrame) -> dict:
    volumes = df["volume"][df["volume"] > 0]  # 0 = volume absent de la source
    adv = _finite(volumes.iloc[-ADV_WINDOW:].mean()) if len(volumes) >= ADV_WINDOW else None

    atr = atr_pct = None
    # Une séance de plus que la fenêtre : le premier True Range n'a pas de veille.
    if len(df) > ATR_WINDOW:
        atr = _finite(average_true_range(df).iloc[-1])
        if atr is not None:
            atr_pct = _finite(atr / df["close"].iloc[-1] * 100)

    returns = _log_returns(df["close"])
    window = _last_year(returns)
    volatility = None
    if window is not None:
        volatility = _finite(window.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100)
    jumps = returns.iloc[-RETURN_WINDOW:]
    jumps = jumps[np.abs(np.expm1(jumps)) > JUMP_THRESHOLD]

    return {
        "as_of": df.index[-1].date(),
        "average_daily_volume": adv,
        "atr": atr,
        "atr_pct": atr_pct,
        "volatility_pct": volatility,
        "suspect_jump_date": jumps.index[-1].date() if len(jumps) else None,
    }


def _index_metrics(close: pd.Series, index_close: pd.Series | None) -> dict:
    empty = {"beta": None, "index_correlation": None}
    if index_close is None:
        return empty
    pairs = pd.concat([close, index_close], axis=1, join="inner", keys=["stock", "index"]).dropna()
    if len(pairs) <= RETURN_WINDOW:
        return empty
    window = _last_year(np.log(pairs).diff().iloc[1:])
    if window is None:
        return empty
    variance = window["index"].var()
    if variance == 0:
        return empty
    return {
        "beta": _finite(window["stock"].cov(window["index"]) / variance),
        "index_correlation": _correlation(window["stock"], window["index"]),
    }


def sector_family(sector: str | None) -> str:
    # Même découpage que `sectorFamily` (web/src/components/torusLayout.js).
    return (sector or "").split(" / ")[0].strip()


def _sector_metrics(returns: pd.Series, peers: pd.DataFrame) -> dict:
    """`peers` : rendements des autres valeurs de la famille, une par colonne."""
    empty = {"sector_correlation": None, "sector_peers": 0}
    window = returns.iloc[-RETURN_WINDOW:]
    if peers.shape[1] < MIN_PEERS or window.empty:
        return empty
    others = peers.reindex(window.index)
    enough = others.count(axis=1) >= MIN_PEERS
    used = int(others[enough].notna().any().sum())
    if enough.sum() < MIN_SECTOR_OBSERVATIONS or (window.index[-1] - window.index[0]).days > MAX_WINDOW_DAYS:
        return empty
    return {
        "sector_correlation": _correlation(window[enough], others[enough].mean(axis=1)),
        "sector_peers": used,
    }


def compute_risk_metrics(
    prices: dict[str, pd.DataFrame],
    sectors: dict[str, str],
    index_close: pd.Series | None,
    today: pd.Timestamp,
) -> list[dict]:
    """Une ligne par titre de `sectors`, y compris ceux sans aucun prix.

    `prices` : `{symbol: OHLCV}` tel que lu en base. `index_close` : clôtures
    de l'indice indexées par date de séance, ou `None` s'il est indisponible.
    `today` : date du jour à Paris, sans fuseau."""
    frames = {s: completed_sessions(df, today) for s, df in prices.items() if s in sectors}
    frames = {s: df for s, df in frames.items() if not df.empty}
    returns = {s: _log_returns(df["close"]) for s, df in frames.items()}
    if index_close is not None:
        index_close = index_close[(index_close.index < today) & (index_close > 0)]

    members: dict[str, dict[str, pd.Series]] = {}
    for symbol, series in returns.items():
        family = sector_family(sectors[symbol])
        if family:
            members.setdefault(family, {})[symbol] = series
    # Un seul alignement par famille, réutilisé pour chacun de ses titres.
    families = {family: pd.concat(series, axis=1) for family, series in members.items()}

    rows = []
    for symbol in sorted(sectors):
        family = sector_family(sectors[symbol])
        row = {
            "symbol": symbol,
            "sector_family": family or None,
            "as_of": None,
            "average_daily_volume": None,
            "atr": None,
            "atr_pct": None,
            "volatility_pct": None,
            "suspect_jump_date": None,
            "beta": None,
            "index_correlation": None,
            "sector_correlation": None,
            "sector_peers": 0,
        }
        if symbol in frames:
            peers = families.get(family, pd.DataFrame()).drop(columns=symbol, errors="ignore")
            row.update(_own_metrics(frames[symbol]))
            row.update(_index_metrics(frames[symbol]["close"], index_close))
            row.update(_sector_metrics(returns[symbol], peers))
        rows.append(row)
    return rows
