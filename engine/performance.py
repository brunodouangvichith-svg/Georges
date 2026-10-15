"""Performance réalisée des décisions clôturées (onglet web "Trading",
ad hoc, pas une phase du roadmap) — pur, sans base ni réseau, même
découpage que `engine/backtest.py` vs `engine/build_training_set.py` :
`api/routers/decisions.py:get_performance` lit la base, ce module calcule.

Ce qui compte comme "réalisé" : uniquement le résultat d'une décision au
statut `cloturee`, c'est-à-dire la ligne `decision_outcomes` écrite par
`POST /decisions/{id}/confirm-exit` (`take_profit_hit` ou `stop_loss_hit`).
`decision_outcomes` contient aussi des lignes `open` écrites par
`engine.reevaluate_decisions` pour des positions encore ouvertes — ce sont
des rendements latents, jamais comptés ici. Une décision peut avoir
plusieurs lignes : `latest_realised_outcomes` ne garde que la plus récente
non-`open`, pour ne jamais compter deux fois la même position.

Limites assumées, affichées à l'écran : `pnl_pct` est brut (ni frais, ni
taille de position — une décision n'a pas de quantité) et `total_pnl_pct`
est une SOMME de pourcentages, pas un rendement composé de portefeuille.
"""

from __future__ import annotations

REALISED_RESULTS = {"take_profit_hit", "stop_loss_hit"}


def latest_realised_outcomes(rows: list[dict]) -> list[dict]:
    """`rows` : une ligne par (décision clôturée, ligne decision_outcomes),
    avec au moins `decision_id`, `result`, `evaluated_at`. Garde, pour
    chaque décision, la ligne réalisée la plus récente ; ignore les `open`.
    Résultat trié du plus récent au plus ancien."""
    latest: dict[int, dict] = {}
    for row in rows:
        if row["result"] not in REALISED_RESULTS:
            continue
        current = latest.get(row["decision_id"])
        if current is None or row["evaluated_at"] > current["evaluated_at"]:
            latest[row["decision_id"]] = row
    return sorted(latest.values(), key=lambda r: r["evaluated_at"], reverse=True)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def stats(trades: list[dict]) -> dict:
    """Statistiques d'un ensemble de trades réalisés (`pnl_pct` en %).
    Un gain = `pnl_pct > 0` ; un trade à 0 % n'est ni gagnant ni perdant.
    Chaque moyenne vaut `None` (jamais 0) quand il n'y a rien à moyenner."""
    pnls = [float(t["pnl_pct"]) for t in trades]
    gains = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    count = len(pnls)
    return {
        "count": count,
        "wins": len(gains),
        "losses": len(losses),
        "win_rate_pct": _round(len(gains) / count * 100) if count else None,
        "avg_pnl_pct": _round(sum(pnls) / count) if count else None,
        "avg_gain_pct": _round(sum(gains) / len(gains)) if gains else None,
        "avg_loss_pct": _round(sum(losses) / len(losses)) if losses else None,
        "total_pnl_pct": _round(sum(pnls)) if count else None,
        "best_pnl_pct": _round(max(pnls)) if count else None,
        "worst_pnl_pct": _round(min(pnls)) if count else None,
    }


def by_pattern(trades: list[dict]) -> list[dict]:
    """Mêmes statistiques par type de figure (`pattern_type`, "Sans figure"
    pour une décision sans figure rattachée), du plus de trades au moins."""
    groups: dict[str, list[dict]] = {}
    for t in trades:
        groups.setdefault(t.get("pattern_type") or "Sans figure", []).append(t)
    rows = [{"pattern_type": name, **stats(items)} for name, items in groups.items()]
    return sorted(rows, key=lambda r: (-r["count"], r["pattern_type"]))


def build_performance(rows: list[dict]) -> dict:
    """Point d'entrée : lignes brutes → {summary, by_pattern, trades}."""
    trades = latest_realised_outcomes(rows)
    return {"summary": stats(trades), "by_pattern": by_pattern(trades), "trades": trades}
