"""Ruptures d'échelle connues dans les séries de prix de yfinance.

Autour de certaines opérations sur titre, la série fournie n'est pas
comparable avec elle-même : l'historique antérieur est multiplié par un
coefficient que les cours suivants ne portent pas, ou pas à la même date.
Les figures, moyennes mobiles et rendements calculés à travers une telle
rupture sont faux. Seule la partie postérieure à la dernière rupture est
donc donnée à l'analyse ; rien n'est modifié en base, et aucun cours n'est
recalculé (les coefficients ne sont pas vérifiés pour toutes les valeurs).

La liste est tenue à la main : un saut de plus d'un facteur 2 est souvent
réel (résultats d'essais cliniques, avertissement sur résultats), seul un
contrôle de l'opération ou de l'annonce permet de trancher —
`ingestion.price_history` signale les sauts récents à contrôler. Détail des
cas contrôlés : `docs/claude/foundations.md`, section « Long-term price
history ».
"""

import datetime

import pandas as pd

# Première séance (date de Paris) de la partie exploitable de chaque série.
FIRST_USABLE_SESSION: dict[str, str] = {
    # Droits de souscription détachés le 12/11/2024 : historique antérieur
    # multiplié par le coefficient théorique (0,0049/0,66), que le cours n'a
    # rejoint que le 06/12/2024.
    "ATO.PA": "2024-12-06",
    # Même forme : droits détachés le 14/11/2023, cours rejoint le 30/11.
    "EMEIS.PA": "2023-11-30",
    # Scission détachée le 16/12/2024, mais la série change d'échelle dès le
    # 09/12 ; l'historique antérieur n'est pas au même niveau.
    "VIV.PA": "2024-12-09",
}


def usable_since(symbol: str) -> datetime.datetime | None:
    """Minuit à Paris de la première séance exploitable de `symbol`, pour
    filtrer en base comme `trim_before_break` ; `None` sans rupture connue."""
    first = FIRST_USABLE_SESSION.get(symbol)
    if first is None:
        return None
    return pd.Timestamp(first, tz="Europe/Paris").to_pydatetime()


def trim_before_break(symbol: str, df: pd.DataFrame) -> pd.DataFrame:
    """`df` (index de dates) sans les séances antérieures à la dernière
    rupture connue de `symbol`. Inchangé pour les autres valeurs."""
    first = FIRST_USABLE_SESSION.get(symbol)
    if first is None or df.empty:
        return df
    dates = pd.DatetimeIndex(df.index)
    # La base renvoie minuit à Paris sous la forme 22 h ou 23 h UTC la veille.
    if dates.tz is not None:
        dates = dates.tz_convert("Europe/Paris").tz_localize(None)
    return df[dates.normalize() >= pd.Timestamp(first)]
