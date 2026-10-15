"""Calculs financiers d'Obligataire Watch (ad hoc, pas une phase du roadmap)
— pur, aucun accès DB, même principe que `engine/george_index.py` : travaille
sur des valeurs déjà chargées, testable sur des cas synthétiques (voir
`tests/test_bond_spread.py`). Le chargement depuis la base et le choix de
l'observation de comparaison pertinente sont faits par
`engine/compute_bond_yields.py`.

Discipline explicitement demandée par le cahier des charges (§7) : ne jamais
confondre pourcentage, point de pourcentage et point de base. Un rendement
qui passe de 3,50 % à 3,60 % varie de +10 points de base (0,10 point de
pourcentage × 100), pas de +0,10 % ni de +10 %. Toutes les fonctions
ci-dessous prennent des valeurs en pourcentage et renvoient un résultat en
points de base (bps) — jamais l'inverse, jamais une valeur en points de
pourcentage présentée comme des bps."""

from __future__ import annotations


def spread_bps(instrument_a_pct: float | None, instrument_b_pct: float | None) -> float | None:
    """Écart en points de base entre deux rendements en pourcentage
    (`(a - b) * 100`) — utilisé pour le spread OAT-Bund. `None` si l'une des
    deux valeurs est manquante, jamais une estimation fabriquée."""
    if instrument_a_pct is None or instrument_b_pct is None:
        return None
    return round((float(instrument_a_pct) - float(instrument_b_pct)) * 100, 1)


def curve_slope_bps(long_maturity_pct: float | None, short_maturity_pct: float | None) -> float | None:
    """Pente de courbe en points de base entre deux maturités d'un même
    émetteur (`(long - short) * 100`) — utilisé pour le 10 ans moins 2 ans
    américain. Une valeur négative signale une courbe inversée (maturité
    courte au-dessus de la longue). `None` si l'une des deux valeurs est
    manquante."""
    if long_maturity_pct is None or short_maturity_pct is None:
        return None
    return round((float(long_maturity_pct) - float(short_maturity_pct)) * 100, 1)


def variation_bps(current_pct: float | None, previous_pct: float | None) -> float | None:
    """Variation en points de base entre deux observations successives d'un
    même rendement (`(actuel - précédent) * 100`). `None` si l'une des deux
    valeurs est manquante — ne jamais comparer une valeur réelle à une
    valeur fabriquée. Ne vérifie délibérément pas la pertinence temporelle
    des deux observations (ex. un écart de plusieurs mois) : c'est le rôle
    de l'appelant (`engine/compute_bond_yields.py`), qui choisit quelle
    observation historique comparer selon la fenêtre demandée (24h/7j/30j)
    et la fraîcheur réelle des données disponibles — voir son docstring."""
    if current_pct is None or previous_pct is None:
        return None
    return round((float(current_pct) - float(previous_pct)) * 100, 1)
