"""Rendu d'un graphique en chandeliers en image PNG (ad hoc, pas une phase
du roadmap) — demandé directement par l'utilisateur pour joindre la courbe
10 ans d'un titre à un partage par email (`notifications/email_client.py`).

Seul consommateur de `mplfinance` en dehors du notebook de validation
(`engine/notebooks/pattern_validation.ipynb`) — promu de l'extra `notebook`
aux dépendances de base (`pyproject.toml`) puisqu'il tourne désormais dans
l'API en production, pas seulement offline."""
import io

import matplotlib

# Backend headless, explicite, avant tout import de mplfinance/pyplot : sans
# ça, matplotlib détecte et utilise le backend GUI installé sur la machine
# (TkAgg ici) — un vrai problème en production, pas juste cosmétique, cette
# fonction tournant dans le threadpool de FastAPI (route `def`, voir
# `api/routers/share.py`) et les backends GUI n'étant pas thread-safe hors du
# thread principal (`RuntimeError: main thread is not in main loop` observé
# en test). `Agg` est le backend standard, headless, pour générer des images
# côté serveur.
matplotlib.use("Agg")

import mplfinance as mpf  # noqa: E402 -- doit suivre matplotlib.use("Agg")
import pandas as pd


def render_candlestick_png(df: pd.DataFrame, title: str) -> bytes:
    """`df` au format `engine.run_detection.load_prices` (colonnes
    minuscules open/high/low/close/volume, index DatetimeIndex) — mplfinance
    attend des colonnes capitalisées, renommées ici plutôt que de changer la
    convention partagée par tout le reste du moteur."""
    plot_df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})

    buffer = io.BytesIO()
    mpf.plot(
        plot_df,
        type="candle",
        style="charles",
        title=title,
        volume=True,
        savefig=dict(fname=buffer, dpi=150, bbox_inches="tight"),
    )
    return buffer.getvalue()
