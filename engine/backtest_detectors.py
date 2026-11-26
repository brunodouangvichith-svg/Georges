"""Backtest walk-forward des 60 détecteurs de figures, coûts de transaction inclus.

But : répondre à « est-ce qu'une figure détectée par George gagne de l'argent
une fois les frais payés ? », détecteur par détecteur, avant de bâtir quoi que
ce soit d'autre dessus (scoring, abonnement, capital réel).

Méthode, sans regard vers le futur :
1. **Signaux** — pour chaque titre et chaque séance `t`, `engine.detect.detect_all`
   ne voit que les `WINDOW` dernières bougies jusqu'à `t` incluse, exactement
   comme le job planifié le voit en production le soir de `t`. Les niveaux
   (objectif/stop) viennent de `engine.exit_levels.propose_levels` avec le
   cours de clôture de `t` comme prix d'entrée théorique — même règle que
   `engine.propose_decisions`.
2. **Trades** — exécution réaliste : achat (ou vente à découvert pour une
   figure baissière) à l'**ouverture de t+1**, puis sortie au premier des trois :
   stop touché, objectif touché, ou `MAX_HOLD` séances écoulées (sortie à la
   clôture). Si stop et objectif sont touchés dans la même séance, on retient
   le stop (hypothèse prudente : l'ordre intra-séance est inconnu). Un écart
   d'ouverture qui saute déjà le stop ou l'objectif annule le trade.
   Une même figure sur un même titre n'ouvre pas de nouveau trade tant que le
   précédent est en cours (sinon une figure qui reste vraie plusieurs jours
   compterait plusieurs fois le même pari).
3. **Coûts** — courtage + glissement à chaque sens, et taxe sur les
   transactions financières (TTF, 0,4 % à l'achat) sur les titres de sociétés
   françaises. Approximation assumée : la TTF ne vise en réalité que les
   sociétés françaises de plus d'un milliard d'euros de capitalisation (liste
   publiée chaque année) ; quelques valeurs du CAC Mid 60 peuvent être
   sous ce seuil. Aucun coût d'emprunt n'est compté pour les ventes à
   découvert (et elles sont impossibles en PEA — le rapport sépare long/short).
4. **Rapport** — par détecteur : nombre de trades, taux de réussite,
   rendement net moyen, profit factor, espérance en R, et stabilité entre la
   période d'apprentissage et les 3 dernières années (hors échantillon). Le
   tout comparé à une base « entrée au hasard » de même durée, pour ne pas
   confondre la dérive haussière du marché avec un vrai avantage.

Limites connues :
- Confiance heuristique uniquement (celle calculée par chaque détecteur), pas
  le modèle XGBoost de `engine.scoring` : celui-ci a été entraîné sur des
  données synthétiques et ses prédictions sur l'historique seraient
  contaminées par son propre entraînement.
- Fenêtre de `WINDOW` séances : les très grandes figures de retournement
  (plusieurs années) que la production peut voir sur 10 ans ne sont pas
  détectées ici.
- Prix non ajustés des dividendes (`auto_adjust=False`, comme
  `ingestion.ohlcv`/`ingestion.price_history`) : fidèle à ce que voit George,
  mais un détachement de dividende ressemble à une baisse.

Commandes :
    python -m engine.backtest_detectors                 # tout l'univers, 4 processus
    python -m engine.backtest_detectors --symbols TTE.PA MC.PA --workers 1
    python -m engine.backtest_detectors --report-only    # recalcule le rapport depuis le cache

Prix : depuis `price_history_long` si `DATABASE_URL` est défini, sinon
téléchargés via yfinance (10 ans). Prix et signaux sont mis en cache sous
`engine/data/backtest/` (non versionné), donc une exécution interrompue
reprend là où elle s'était arrêtée.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

from engine.detect import detect_all
from engine.exit_levels import is_bullish, propose_levels

logger = logging.getLogger(__name__)

WINDOW = 300  # séances vues par les détecteurs à chaque date (≥ 200 pour la SMA200)
MAX_HOLD = 20  # séances maximum en position
OUT_OF_SAMPLE_YEARS = 3
BASELINE_HOLD = 10  # durée de la base « entrée au hasard »

CACHE_DIR = Path(__file__).resolve().parent / "data" / "backtest"
PRICES_DIR = CACHE_DIR / "prices"
SIGNALS_DIR = CACHE_DIR / "signals"


@dataclass(frozen=True)
class Costs:
    """Coûts en fraction du montant (0.001 = 0,1 %)."""

    commission: float = 0.001  # par sens (courtier en ligne type, ordre de quelques milliers d'euros)
    slippage: float = 0.0005  # par sens
    ftt: float = 0.004  # TTF française, à l'achat uniquement

    def round_trip(self, bullish: bool, french_equity: bool) -> float:
        """Coût total aller-retour. La TTF s'applique à l'acquisition de
        titres : à l'entrée pour un achat, au rachat pour une vente à
        découvert."""
        cost = 2 * (self.commission + self.slippage)
        if french_equity:
            cost += self.ftt
        return cost


@dataclass
class Trade:
    symbol: str
    pattern_type: str
    bullish: bool
    confidence: float
    signal_date: pd.Timestamp
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry: float
    exit: float
    take_profit: float
    stop_loss: float
    outcome: str  # "objectif" | "stop" | "duree"
    bars_held: int
    gross_return: float
    net_return: float
    risk: float  # distance entrée-stop, en fraction du prix d'entrée
    r_multiple: float


# --- Prix -----------------------------------------------------------------


def universe() -> list[tuple[str, str]]:
    """`[(symbol, country), ...]` — même univers que `ingestion.seed`."""
    from ingestion.cac40 import CAC40_SECURITIES
    from ingestion.cac_mid60 import CAC_MID60_SECURITIES

    return [(row[0], row[2]) for row in CAC40_SECURITIES + CAC_MID60_SECURITIES]


def load_symbol_prices(symbol: str) -> pd.DataFrame:
    """Prix quotidiens d'un titre, avec cache disque."""
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    path = PRICES_DIR / f"{symbol}.parquet"
    if path.exists():
        return pd.read_parquet(path)

    if os.environ.get("DATABASE_URL"):
        from engine.run_detection import load_prices
        from ingestion.db import get_engine

        df = load_prices(get_engine(), symbol)
    else:
        from ingestion.ohlcv import download_symbol

        df = download_symbol(symbol, period="10y")

    if df is None or df.empty:
        # Pas de mise en cache d'un échec : un throttling yfinance passager ne
        # doit pas exclure ce titre de toutes les exécutions suivantes.
        logger.warning("Aucun prix pour %s, titre ignoré (non mis en cache).", symbol)
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = df[df["close"].notna()].copy()
    idx = pd.to_datetime(df.index)
    # Date de séance à l'heure de Paris : yfinance renvoie minuit Europe/Paris,
    # la base renvoie le même instant en UTC (22 h/23 h la veille). Sans
    # conversion préalable, `normalize()` daterait la séance de la veille.
    if idx.tz is not None:
        idx = idx.tz_convert("Europe/Paris").tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    df.to_parquet(path)
    return df


# --- Signaux --------------------------------------------------------------


def generate_signals(df: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    """Rejoue la détection séance par séance. Une ligne par figure confirmée
    sur la dernière bougie visible, avec ses niveaux. `signal_pos` est la
    position de la séance de signal dans `df`."""
    rows = []
    for end in range(window - 1, len(df) - 1):  # la dernière séance n'a pas de lendemain pour entrer
        sub = df.iloc[end - window + 1 : end + 1]
        last_ts = sub.index[-1]
        entry_price = float(sub["close"].iloc[-1])
        for match in detect_all(sub):
            if match.detected_at != last_ts:
                continue
            try:
                take_profit, stop_loss = propose_levels(match.pattern_type, match.context, entry_price, sub)
            except (KeyError, ValueError, IndexError, ZeroDivisionError):
                continue
            if not (math.isfinite(take_profit) and math.isfinite(stop_loss)):
                continue
            rows.append(
                {
                    "signal_pos": end,
                    "signal_date": last_ts,
                    "pattern_type": match.pattern_type,
                    "bullish": is_bullish(match.pattern_type),
                    "confidence": float(match.confidence),
                    "take_profit": float(take_profit),
                    "stop_loss": float(stop_loss),
                }
            )
    return pd.DataFrame(
        rows,
        columns=["signal_pos", "signal_date", "pattern_type", "bullish", "confidence", "take_profit", "stop_loss"],
    )


def detection_fingerprint() -> str:
    """Empreinte du code qui produit les signaux (détecteurs, scores, niveaux)
    et de `WINDOW`. Elle change dès qu'une règle change, ce qui invalide le
    cache des signaux."""
    import hashlib

    engine_dir = Path(__file__).resolve().parent
    files = sorted((engine_dir / "patterns").glob("*.py")) + [
        engine_dir / "exit_levels.py",
        engine_dir / "confidence.py",
        engine_dir / "detect.py",
    ]
    digest = hashlib.sha256(f"window={WINDOW}".encode())
    for f in files:
        digest.update(f.name.encode())
        digest.update(f.read_bytes())
    return digest.hexdigest()[:16]


def ensure_signal_cache_is_current() -> None:
    """Vide le cache des signaux s'il a été produit par un autre code de
    détection. Un cache sans empreinte (exécutions antérieures) est adopté
    tel quel, avec un avertissement."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    meta = SIGNALS_DIR / "_empreinte.txt"
    current = detection_fingerprint()
    if meta.exists():
        if meta.read_text().strip() != current:
            stale = list(SIGNALS_DIR.glob("*.parquet"))
            logger.warning("Code de détection modifié : %s fichiers de signaux recalculés.", len(stale))
            for f in stale:
                f.unlink()
    elif any(SIGNALS_DIR.glob("*.parquet")):
        logger.warning("Cache de signaux sans empreinte : supposé produit par le code actuel.")
    meta.write_text(current)


def symbol_signals(symbol: str) -> tuple[str, int]:
    """Calcule (ou relit du cache) les signaux d'un titre. Pensé pour `Pool.imap`."""
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    path = SIGNALS_DIR / f"{symbol}.parquet"
    if path.exists():
        return symbol, len(pd.read_parquet(path))
    df = load_symbol_prices(symbol)
    signals = generate_signals(df) if len(df) > WINDOW else generate_signals(df.iloc[:0])
    signals.to_parquet(path)
    return symbol, len(signals)


# --- Trades ---------------------------------------------------------------


def simulate_trade(
    df: pd.DataFrame,
    signal_pos: int,
    bullish: bool,
    take_profit: float,
    stop_loss: float,
    costs: Costs,
    french_equity: bool,
    max_hold: int = MAX_HOLD,
    arrays: tuple | None = None,
) -> dict | None:
    """Simule un trade entré à l'ouverture de `signal_pos + 1`. Renvoie `None`
    si le trade n'est pas jouable (plus de données, niveaux incohérents,
    ouverture qui a déjà sauté le stop/l'objectif) ou encore en cours à la
    fin des données (son résultat n'est pas connu). `arrays` =
    `(opens, highs, lows, closes)` déjà extraits, pour éviter de les
    recalculer à chaque signal."""
    entry_pos = signal_pos + 1
    if entry_pos >= len(df):
        return None

    opens, highs, lows, closes = arrays if arrays is not None else _price_arrays(df)

    entry = opens[entry_pos]
    if not (entry > 0):
        return None
    if bullish and not (stop_loss < entry < take_profit):
        return None
    if not bullish and not (take_profit < entry < stop_loss):
        return None

    planned_last = entry_pos + max_hold - 1
    last_pos = min(planned_last, len(df) - 1)
    exit_price, exit_pos, outcome = closes[last_pos], last_pos, "duree"
    for pos in range(entry_pos, last_pos + 1):
        o, h, l = opens[pos], highs[pos], lows[pos]
        if bullish:
            stop_hit, target_hit = l <= stop_loss, h >= take_profit
        else:
            stop_hit, target_hit = h >= stop_loss, l <= take_profit
        if stop_hit:
            # Ouverture déjà au-delà du stop (écart de cotation) : exécution à l'ouverture.
            gap_through = (o < stop_loss) if bullish else (o > stop_loss)
            exit_price = o if (pos > entry_pos and gap_through) else stop_loss
            exit_pos, outcome = pos, "stop"
            break
        if target_hit:
            gap_through = (o > take_profit) if bullish else (o < take_profit)
            exit_price = o if (pos > entry_pos and gap_through) else take_profit
            exit_pos, outcome = pos, "objectif"
            break

    if outcome == "duree" and last_pos < planned_last:
        return None  # position encore ouverte à la fin des données

    direction = 1.0 if bullish else -1.0
    gross = direction * (exit_price - entry) / entry
    net = gross - costs.round_trip(bullish, french_equity)
    risk = abs(entry - stop_loss) / entry
    return {
        "entry_pos": entry_pos,
        "exit_pos": exit_pos,
        "entry": float(entry),
        "exit": float(exit_price),
        "outcome": outcome,
        "bars_held": exit_pos - entry_pos + 1,
        "gross_return": float(gross),
        "net_return": float(net),
        "risk": float(risk),
        "r_multiple": float(net / risk) if risk > 0 else float("nan"),
    }


def _price_arrays(df: pd.DataFrame) -> tuple:
    return tuple(df[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close"))


def run_trades(
    symbol: str,
    df: pd.DataFrame,
    signals: pd.DataFrame,
    costs: Costs,
    french_equity: bool,
    max_hold: int = MAX_HOLD,
) -> list[Trade]:
    """Transforme les signaux d'un titre en trades, sans empiler deux trades
    simultanés de la même figure sur ce titre."""
    trades: list[Trade] = []
    busy_until: dict[str, int] = {}
    arrays = _price_arrays(df)
    # Position retrouvée par la date, pas par `signal_pos` stocké : si le
    # cache de prix a été retéléchargé entre-temps (fenêtre de 10 ans décalée),
    # les positions stockées ne correspondraient plus aux bonnes séances.
    signals = signals.assign(pos=df.index.get_indexer(pd.to_datetime(signals["signal_date"])))
    signals = signals[signals["pos"] >= 0]
    for sig in signals.sort_values("pos").itertuples(index=False):
        if sig.pos < busy_until.get(sig.pattern_type, -1):
            continue
        result = simulate_trade(
            df, int(sig.pos), bool(sig.bullish), sig.take_profit, sig.stop_loss, costs, french_equity, max_hold, arrays
        )
        if result is None:
            continue
        busy_until[sig.pattern_type] = result["exit_pos"]
        trades.append(
            Trade(
                symbol=symbol,
                pattern_type=sig.pattern_type,
                bullish=bool(sig.bullish),
                confidence=float(sig.confidence),
                signal_date=pd.Timestamp(sig.signal_date),
                entry_date=df.index[result["entry_pos"]],
                exit_date=df.index[result["exit_pos"]],
                entry=result["entry"],
                exit=result["exit"],
                take_profit=float(sig.take_profit),
                stop_loss=float(sig.stop_loss),
                outcome=result["outcome"],
                bars_held=result["bars_held"],
                gross_return=result["gross_return"],
                net_return=result["net_return"],
                risk=result["risk"],
                r_multiple=result["r_multiple"],
            )
        )
    return trades


def baseline_returns(df: pd.DataFrame, costs: Costs, french_equity: bool, hold: int = BASELINE_HOLD) -> dict[str, float]:
    """Rendement net moyen d'une entrée à l'ouverture de n'importe quelle
    séance, revendue `hold` séances plus tard à la clôture — la « figure
    aléatoire » à battre. Renvoie la somme et le nombre, pour agréger
    plusieurs titres sans biais de pondération."""
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    if len(df) <= WINDOW + hold:
        return {"long_sum": 0.0, "short_sum": 0.0, "n": 0}
    start = WINDOW  # mêmes séances que celles où un signal pourrait être exécuté
    entry = opens[start : len(df) - hold + 1]
    exit_ = closes[start + hold - 1 :]
    valid = entry > 0
    move = (exit_[valid] - entry[valid]) / entry[valid]
    return {
        "long_sum": float(np.sum(move - costs.round_trip(True, french_equity))),
        "short_sum": float(np.sum(-move - costs.round_trip(False, french_equity))),
        "n": int(valid.sum()),
    }


# --- Rapport --------------------------------------------------------------


def summarize(trades: pd.DataFrame) -> dict:
    """Statistiques d'un groupe de trades."""
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    net = trades["net_return"]
    wins, losses = net[net > 0], net[net <= 0]
    std = net.std(ddof=1) if n > 1 else float("nan")
    return {
        "trades": n,
        "reussite_pct": 100 * len(wins) / n,
        "brut_moyen_pct": 100 * trades["gross_return"].mean() if "gross_return" in trades else float("nan"),
        "net_moyen_pct": 100 * net.mean(),
        "net_median_pct": 100 * net.median(),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if losses.sum() < 0 else float("inf"),
        # Rapport des moyennes plutôt que moyenne des R : un stop placé à
        # quelques centimes de l'entrée donnerait des R énormes qui
        # écraseraient tout le reste.
        "esperance_R": float(net.mean() / trades["risk"].mean())
        if "risk" in trades and trades["risk"].mean() > 0
        else float(trades["r_multiple"].mean()),
        "duree_moy": float(trades["bars_held"].mean()),
        "t_stat": float(net.mean() / (std / math.sqrt(n))) if n > 1 and std > 0 else float("nan"),
    }


def verdict(overall: dict, in_sample: dict, out_sample: dict, min_trades: int = 30, hurdle_pct: float = 0.0) -> str:
    """Classement volontairement exigeant : un avantage doit être positif
    sur les deux périodes, statistiquement net, et faire mieux qu'une entrée
    au hasard dans le même sens (`hurdle_pct`, la dérive du marché), sinon
    on ne le croit pas."""
    if overall.get("trades", 0) < min_trades:
        return "trop peu de trades"
    is_mean, oos_mean = in_sample.get("net_moyen_pct"), out_sample.get("net_moyen_pct")
    if is_mean is None or oos_mean is None:
        return "trop peu de trades"
    bar = max(0.0, hurdle_pct)
    if overall["net_moyen_pct"] > bar and is_mean > 0 and oos_mean > 0 and overall["t_stat"] >= 2:
        return "avantage"
    if overall["net_moyen_pct"] < 0 and is_mean < 0 and oos_mean < 0:
        return "à écarter"
    return "incertain"


def build_report(trades: pd.DataFrame, cutoff: pd.Timestamp, baseline: dict | None = None) -> pd.DataFrame:
    """Une ligne par figure, triée du plus prometteur au moins prometteur.
    `baseline` (voir `run_backtest`) fixe la barre à franchir par sens."""
    baseline = baseline or {}
    rows = []
    for pattern_type, group in trades.groupby("pattern_type"):
        overall = summarize(group)
        in_sample = summarize(group[group["signal_date"] < cutoff])
        out_sample = summarize(group[group["signal_date"] >= cutoff])
        bullish = bool(group["bullish"].iloc[0])
        hurdle = baseline.get("achat_au_hasard_pct" if bullish else "vente_au_hasard_pct", 0.0)
        rows.append(
            {
                "figure": pattern_type,
                "sens": "achat" if bullish else "vente",
                **overall,
                "net_moyen_avant_pct": in_sample.get("net_moyen_pct"),
                "net_moyen_3ans_pct": out_sample.get("net_moyen_pct"),
                "trades_3ans": out_sample.get("trades", 0),
                "verdict": verdict(overall, in_sample, out_sample, hurdle_pct=hurdle),
            }
        )
    report = pd.DataFrame(rows)
    order = {"avantage": 0, "incertain": 1, "à écarter": 2, "trop peu de trades": 3}
    return report.sort_values(["verdict", "net_moyen_pct"], key=lambda s: s.map(order) if s.name == "verdict" else -s)


def confidence_table(trades: pd.DataFrame) -> pd.DataFrame:
    """La confiance affichée par George trie-t-elle vraiment les bons trades ?"""
    bins = [0, 40, 50, 60, 70, 101]
    labels = ["< 40", "40-50", "50-60", "60-70", "≥ 70"]
    bucket = pd.cut(trades["confidence"], bins=bins, labels=labels, right=False)
    rows = []
    for label in labels:
        stats = summarize(trades[bucket == label])
        rows.append({"confiance": label, **stats})
    return pd.DataFrame(rows)


def run_backtest(symbols: list[tuple[str, str]], costs: Costs, max_hold: int = MAX_HOLD):
    """Phase rapide : à partir des signaux en cache, simule les trades et
    calcule le rapport. Renvoie `(trades, report, confidence, baseline)`."""
    all_trades: list[Trade] = []
    base = {"long_sum": 0.0, "short_sum": 0.0, "n": 0}
    first_dates, last_dates = [], []
    for symbol, country in symbols:
        sig_path = SIGNALS_DIR / f"{symbol}.parquet"
        if not sig_path.exists():
            continue
        df = load_symbol_prices(symbol)
        if df.empty:
            continue
        french = country == "FR"
        signals = pd.read_parquet(sig_path)
        all_trades.extend(run_trades(symbol, df, signals, costs, french, max_hold))
        b = baseline_returns(df, costs, french)
        for k in base:
            base[k] += b[k]
        first_dates.append(df.index[0])
        last_dates.append(df.index[-1])

    trades = pd.DataFrame([asdict(t) for t in all_trades])
    if trades.empty:
        return trades, pd.DataFrame(), pd.DataFrame(), {}
    end = max(last_dates)
    cutoff = end - pd.DateOffset(years=OUT_OF_SAMPLE_YEARS)
    baseline = {
        "achat_au_hasard_pct": 100 * base["long_sum"] / base["n"] if base["n"] else float("nan"),
        "vente_au_hasard_pct": 100 * base["short_sum"] / base["n"] if base["n"] else float("nan"),
        "duree": BASELINE_HOLD,
        "debut": min(first_dates),
        "fin": end,
        "coupure_hors_echantillon": cutoff,
    }
    return trades, build_report(trades, cutoff, baseline), confidence_table(trades), baseline


def _fmt(report: pd.DataFrame) -> str:
    cols = [
        "figure", "sens", "trades", "reussite_pct", "brut_moyen_pct", "net_moyen_pct", "profit_factor",
        "esperance_R", "net_moyen_avant_pct", "net_moyen_3ans_pct", "t_stat", "verdict",
    ]
    return report[cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--symbols", nargs="*", help="limiter à ces titres (ex. TTE.PA MC.PA)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-hold", type=int, default=MAX_HOLD)
    parser.add_argument("--report-only", action="store_true", help="ne recalcule aucun signal, relit le cache")
    args = parser.parse_args()
    # La console Windows (cp1252) ne sait pas afficher « → » ni « ≥ ».
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    symbols = universe()
    if args.symbols:
        wanted = set(args.symbols)
        symbols = [s for s in symbols if s[0] in wanted]

    if args.report_only:
        meta = SIGNALS_DIR / "_empreinte.txt"
        if meta.exists() and meta.read_text().strip() != detection_fingerprint():
            logger.warning("Le cache de signaux vient d'un autre code de détection : relancer sans --report-only.")
    else:
        ensure_signal_cache_is_current()
        # Les prix d'abord, en série : yfinance supporte mal les appels parallèles.
        for symbol, _ in symbols:
            load_symbol_prices(symbol)
        started = time.time()
        names = [s for s, _ in symbols]
        with Pool(processes=max(1, args.workers)) as pool:
            for k, (symbol, count) in enumerate(pool.imap_unordered(symbol_signals, names), 1):
                logger.info("[%s/%s] %s : %s signaux (%.0f min écoulées)", k, len(names), symbol, count, (time.time() - started) / 60)

    costs = Costs()
    trades, report, confidence, baseline = run_backtest(symbols, costs, args.max_hold)
    if trades.empty:
        print("Aucun trade : rien en cache pour ces titres.")
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    trades.to_csv(CACHE_DIR / "trades.csv", index=False)
    report.to_csv(CACHE_DIR / "rapport_figures.csv", index=False)
    confidence.to_csv(CACHE_DIR / "rapport_confiance.csv", index=False)

    pd.set_option("display.width", 220)
    print(f"\nPériode {baseline['debut']:%Y-%m-%d} → {baseline['fin']:%Y-%m-%d}, hors échantillon depuis {baseline['coupure_hors_echantillon']:%Y-%m-%d}")
    print(f"Coûts : {asdict(costs)}  ·  sortie au plus tard après {args.max_hold} séances")
    print(f"Base à battre ({BASELINE_HOLD} séances, frais inclus) : achat au hasard {baseline['achat_au_hasard_pct']:.2f} %, vente au hasard {baseline['vente_au_hasard_pct']:.2f} %\n")
    print(_fmt(report))
    print("\nPar niveau de confiance :")
    print(confidence.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    for side, mask in (("Achats", trades["bullish"]), ("Ventes", ~trades["bullish"])):
        s = summarize(trades[mask])
        if s["trades"]:
            print(f"\n{side} : {s['trades']} trades, réussite {s['reussite_pct']:.1f} %, net moyen {s['net_moyen_pct']:.2f} %, PF {s['profit_factor']:.2f}")


if __name__ == "__main__":
    main()
