"""Indicateur de risque obligataire français du rapport stratégique
(vert / orange / rouge) — pur, sans base ni réseau, testable seul.

Seuils de suivi construits pour ce rapport (repris du modèle de rapport
fourni par l'utilisateur), **pas des seuils officiels de crise** — dit
explicitement dans le rapport lui-même :
- rouge  : OAT 10 ans > 5,0 % ET spread OAT-Bund > 150 pb ;
- vert   : spread OAT-Bund < 120 pb ET OAT 10 ans < 4,5 % ;
- orange : tout le reste (vigilance).
Sans OAT ou sans spread exploitable, le niveau est "indetermine" plutôt
qu'un orange par défaut : un indicateur ne doit jamais avoir l'air mesuré
quand il ne l'est pas.
"""

from __future__ import annotations

RED_OAT_PCT = 5.0
RED_SPREAD_BPS = 150.0
GREEN_OAT_PCT = 4.5
GREEN_SPREAD_BPS = 120.0

RISK_LEVELS = ("vert", "orange", "rouge", "indetermine")


def bond_risk_level(oat_10y_pct: float | None, spread_oat_bund_bps: float | None) -> str:
    if oat_10y_pct is None or spread_oat_bund_bps is None:
        return "indetermine"
    if oat_10y_pct > RED_OAT_PCT and spread_oat_bund_bps > RED_SPREAD_BPS:
        return "rouge"
    if spread_oat_bund_bps < GREEN_SPREAD_BPS and oat_10y_pct < GREEN_OAT_PCT:
        return "vert"
    return "orange"


def _fr(value: float) -> str:
    """Nombre à une décimale avec virgule (texte affiché en français)."""
    return f"{value:.1f}".replace(".", ",")


def risk_criteria() -> dict:
    """Les seuils eux-mêmes, recopiés dans le rapport pour que le lecteur voie
    sur quoi repose le niveau affiché."""
    return {
        "rouge": f"OAT 10 ans > {_fr(RED_OAT_PCT)} % et spread OAT-Bund > {RED_SPREAD_BPS:.0f} pb",
        "vert": f"spread OAT-Bund < {GREEN_SPREAD_BPS:.0f} pb et OAT 10 ans < {_fr(GREEN_OAT_PCT)} %",
        "orange": "entre les deux : vigilance",
    }
