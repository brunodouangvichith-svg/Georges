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
import numpy as np
import pandas as pd

# Même principe que `web/src/components/CandlestickChart.jsx`/
# `mobile/lib/features/univers/widgets/candlestick_chart.dart`/
# `engine/notebooks/pattern_validation.ipynb:plot_match` — l'overlay se
# dérive de la *forme* du `context` d'un détecteur (points {index/points,
# price}, niveaux resistance/support), jamais du nom de la figure : une
# quatrième copie de la même logique plutôt qu'un partage cross-langage
# (Python/JS/Dart), même arbitrage que les trois précédentes. `left_rim`/
# `right_rim`/`handle_low` (Cup & Handle) jouent le même rôle conceptuel que
# resistance/support sous un nom différent -- ajoutés ici et dans les deux
# autres implémentations (JS/Dart, tenues en synchronisation) après qu'un
# email de partage réel a montré un Cup & Handle sans aucune ligne tracée.
_LEVEL_KEYS = {"resistance", "support", "left_rim", "right_rim", "handle_low"}


def _build_overlay(context: dict | None) -> tuple[list[tuple[int, float]], list[float]]:
    markers: list[tuple[int, float]] = []
    hlines: list[float] = []
    if not context:
        return markers, hlines

    for key, value in context.items():
        if isinstance(value, dict) and "price" in value:
            price = float(value["price"])
            if "index" in value:
                markers.append((int(value["index"]), price))
            if "points" in value:
                markers.extend((int(i), price) for i in value["points"])
            if "points" in value or key in _LEVEL_KEYS:
                hlines.append(price)
        elif key in _LEVEL_KEYS and isinstance(value, (int, float)):
            hlines.append(float(value))
    return markers, hlines


def render_candlestick_png(
    df: pd.DataFrame,
    title: str,
    context: dict | None = None,
    take_profit: float | None = None,
    stop_loss: float | None = None,
) -> bytes:
    """`df` au format `engine.run_detection.load_prices` (colonnes
    minuscules open/high/low/close/volume, index DatetimeIndex) — mplfinance
    attend des colonnes capitalisées, renommées ici plutôt que de changer la
    convention partagée par tout le reste du moteur.

    `context` (optionnel) : `patterns_detected.context` de la figure la plus
    récente pour ce titre — si fourni, surligne ses points clés (marqueurs)
    et niveaux (resistance/support/neckline, en ligne horizontale), pour que
    le graphique joint à l'email montre la même figure que celle déjà
    affichée dans l'application, pas juste un historique de prix nu.

    `take_profit`/`stop_loss` (optionnels) : niveaux de la décision associée
    (`decisions.take_profit`/`stop_loss`), tracés en vert/rouge — mêmes
    couleurs que `web/src/components/CandlestickChart.jsx`/
    `mobile/.../candlestick_chart.dart`, distinctes du bleu des niveaux de
    figure ci-dessus pour ne pas les confondre."""
    plot_df = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})

    plot_kwargs = dict(type="candle", style="charles", title=title, volume=True)

    markers, pattern_hlines = _build_overlay(context)
    if markers:
        marker_series = pd.Series(np.nan, index=plot_df.index)
        for pos, price in markers:
            if 0 <= pos < len(marker_series):
                marker_series.iloc[pos] = price
        plot_kwargs["addplot"] = [
            mpf.make_addplot(marker_series, type="scatter", markersize=120, marker="o", color="orange")
        ]

    hlines = list(pattern_hlines)
    colors = ["tab:blue"] * len(pattern_hlines)
    if take_profit is not None:
        hlines.append(float(take_profit))
        colors.append("tab:green")
    if stop_loss is not None:
        hlines.append(float(stop_loss))
        colors.append("tab:red")
    # mplfinance rejette hlines=None : la clé doit être absente plutôt que
    # valoir None quand il n'y a aucun niveau à tracer (même piège déjà
    # documenté pour `engine/notebooks/pattern_validation.ipynb`).
    if hlines:
        plot_kwargs["hlines"] = dict(hlines=hlines, colors=colors, linestyle="--")

    buffer = io.BytesIO()
    mpf.plot(plot_df, **plot_kwargs, savefig=dict(fname=buffer, dpi=150, bbox_inches="tight"))
    return buffer.getvalue()
