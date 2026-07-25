"""Orchestrateur pur (aucun accès DB) : exécute tous les détecteurs de
`engine/patterns/` sur un DataFrame OHLCV et renvoie la liste des figures
trouvées. Séparé de `run_detection.py` (qui lit/écrit en base) pour rester
testable sans dépendance à PostgreSQL.
"""

from engine.patterns import DETECTORS, PatternMatch

REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


def detect_all(df) -> list[PatternMatch]:
    """`df` : DataFrame OHLCV indexé par date, trié chronologiquement,
    colonnes `open, high, low, close, volume`. Renvoie la liste des figures
    détectées et confirmées (une par type de pattern au plus, la plus
    récente — voir les modules de `engine/patterns/`)."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"colonnes manquantes dans le DataFrame OHLCV : {sorted(missing)}")

    matches: list[PatternMatch] = []
    for detector in DETECTORS.values():
        matches.extend(detector(df))
    return matches
