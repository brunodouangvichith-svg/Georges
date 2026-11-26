"""Clôtures du CAC 40 (`^FCHI`) pour le bêta et la corrélation de l'écran
Univers. L'indice n'est pas stocké en base (choix de l'utilisateur) : il est
téléchargé chez Yahoo à la demande et gardé en mémoire.

Un échec dégrade vers « indisponible » (``None``), il ne fait jamais échouer
la requête. Une seule tentative, sans attente : cet appel a lieu pendant une
requête HTTP.
"""

import logging
import threading
import time

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

INDEX_TICKER = "^FCHI"
INDEX_NAME = "CAC 40"
PERIOD = "2y"
TIMEOUT_SECONDS = 10
CACHE_SECONDS = 6 * 3600
RETRY_SECONDS = 300  # après un échec, pour ne pas solliciter Yahoo à chaque requête

_lock = threading.Lock()
_cache: dict = {"closes": None, "expires_at": 0.0}


def _download() -> pd.Series | None:
    try:
        history = yf.Ticker(INDEX_TICKER).history(
            period=PERIOD, interval="1d", auto_adjust=False, timeout=TIMEOUT_SECONDS
        )
        closes = history["Close"].dropna()
        if closes.empty:
            logger.warning("Aucun cours reçu pour %s.", INDEX_TICKER)
            return None
        # yfinance date les séances à minuit heure de la place (Paris).
        dates = pd.DatetimeIndex(closes.index)
        if dates.tz is not None:
            dates = dates.tz_convert("Europe/Paris").tz_localize(None)
        closes.index = dates.normalize()
        closes = closes[~closes.index.duplicated(keep="last")].astype(float).sort_index()
        # La barre du jour peut être prise en cours de séance : écartée dès le
        # téléchargement, sinon une série resservie le lendemain la garderait.
        completed = closes[closes.index < pd.Timestamp.now(tz="Europe/Paris").tz_localize(None).normalize()]
        return None if completed.empty else completed
    except Exception as exc:  # noqa: BLE001 - réseau/yfinance : dégrade vers "indisponible"
        logger.warning("Cours du CAC 40 indisponibles : %s", exc)
        return None


def cac40_closes() -> pd.Series | None:
    """Clôtures indexées par date de séance. En cas d'échec, la dernière série
    obtenue est resservie (sa date est affichée) ; ``None`` s'il n'y en a pas."""
    with _lock:
        if time.monotonic() < _cache["expires_at"]:
            return _cache["closes"]
        closes = _download()
        if closes is not None:
            _cache["closes"] = closes
        _cache["expires_at"] = time.monotonic() + (CACHE_SECONDS if closes is not None else RETRY_SECONDS)
        return _cache["closes"]
