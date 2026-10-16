"""Rapport stratégique hebdomadaire — France, marchés et CAC 40 (ad hoc, pas
une phase du roadmap). Demandé directement par l'utilisateur sur le modèle
d'un rapport qu'il avait obtenu ailleurs ; généré à la demande (bouton de
l'onglet « Rapport », web et mobile) via `api/routers/strategic_reports.py`.

Même contrat anti-hallucination que le reste de `agents/` :
1. **Tout ce qui est chiffré est calculé en Python** à partir de la base de
   George (rendements OAT/Bund/Treasuries et spread, Brent, décisions de
   George sur les 40 valeurs, portefeuille virtuel) ou d'appels déterministes
   (clôture du CAC 40 via yfinance, extraits d'articles Tavily numérotés).
   Ces données sont stockées telles quelles dans `StrategicReport.data` et
   affichées par l'interface sans passer par le LLM.
2. **Le LLM ne fait que commenter** ce contexte (`agents/prompts/
   strategic_report_system.txt`) : il ne peut citer que des chiffres présents
   dans le contexte, et doit renvoyer à la source web numérotée `[n]` pour
   tout chiffre qui vient d'un article.
3. **Le portefeuille virtuel** (capital initial 100 000 €) suit des règles
   déterministes (`engine/virtual_portfolio.py`) appliquées aux décisions déjà
   produites par George — jamais un choix de titres fait par le LLM.

Les accès réseau (Tavily, yfinance, Mistral) se font **hors de toute session
base de données** : avec un pool limité à 2 + 2 connexions
(`ingestion/db.py`), garder une connexion ouverte pendant un appel LLM d'une
minute affamerait le reste de l'API.
"""

from __future__ import annotations

import datetime
import json
import logging

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from agents import mistral_client, web_search
from agents.web_search import WebSearchUnavailableError
from engine import virtual_portfolio as vp
from engine.compute_bond_yields import build_dashboard_summary
from engine.strategic_risk import bond_risk_level, risk_criteria
from ingestion.models import (
    BOND_INSTRUMENT_BUND_DE_10Y,
    BOND_INSTRUMENT_OAT_FR_10Y,
    Decision,
    EnergyPriceSnapshot,
    GeopoliticalKnowledge,
    PatternDetected,
    PriceHistoryLong,
    Security,
    StrategicReport,
    VirtualPortfolioSnapshot,
    VirtualPortfolioTrade,
)

logger = logging.getLogger(__name__)

CAC40_THEME = "CAC 40"
CAC40_INDEX_TICKER = "^FCHI"
# Libellé affiché (et signal) pour une décision dont George a proposé ou
# confirmé la sortie : `engine/monitor_decisions.py` passe le statut à
# `sortie_proposee` sans changer `decision_type` (qui reste "Achat") — lire
# seulement `decision_type` ferait d'une sortie un signal d'achat.
EXIT_STATUS_LABELS = {"sortie_proposee": "Sortie proposée", "cloturee": "Clôturée"}
PRICE_LOOKBACK_DAYS = 20
WEEK_SESSIONS = 5
# Une clôture plus vieille que la plus récente de l'univers moins ce délai
# est considérée périmée (flux de prix arrêté) : pas d'ordre à ce prix-là.
STALE_PRICE_DAYS = 5
# Verrou consultatif Postgres pris à l'écriture des ordres : deux générations
# simultanées (déploiement Render qui se chevauche, CLI lancée pendant un job
# web) ne peuvent pas acheter deux fois.
PORTFOLIO_LOCK_KEY = 74_221_001
ENERGY_CODES = ("BRENT_CRUDE_USD", "WTI_USD", "NATURAL_GAS_USD")

# Une requête par thème du rapport. 3 résultats chacune, actualités des 10
# derniers jours seulement : ~6 appels Tavily par rapport généré à la demande.
WEB_QUERIES = [
    ("Finances publiques", "France déficit public dette publique Insee budget"),
    ("Croissance, emploi, inflation", "France inflation chômage croissance PIB Insee"),
    ("Budget 2027", "projet de loi de finances 2027 France déficit Parlement"),
    ("Obligations", "OAT 10 ans spread Bund adjudication Agence France Trésor"),
    ("Crédit immobilier", "taux crédit immobilier France Banque de France"),
    ("CAC 40", "CAC 40 semaine Bourse de Paris entreprises résultats"),
]
WEB_RESULTS_PER_QUERY = 3
WEB_NEWS_DAYS = 10
WEB_EXTRACT_MAX_CHARS = 1200

PROMPT_NAME = "strategic_report_system.txt"


def _f(value) -> float | None:
    return None if value is None else float(value)


# ---------------------------------------------------------------- collecte DB


def _cac40_securities(db: Session) -> list[Security]:
    stmt = select(Security).where(Security.theme == CAC40_THEME).order_by(Security.name)
    return list(db.execute(stmt).scalars())


def _latest_decisions(db: Session, symbols: list[str]) -> dict[str, dict]:
    """Décision la plus récente par valeur, quel que soit son statut (une
    décision clôturée ou en sortie compte : c'est un signal de vente), avec le
    type de figure qui l'a motivée quand il est connu."""
    stmt = (
        select(Decision, PatternDetected.pattern_type)
        .outerjoin(PatternDetected, PatternDetected.id == Decision.pattern_id)
        .where(Decision.symbol.in_(symbols))
        .order_by(Decision.symbol, Decision.created_at.desc(), Decision.id.desc())
    )
    latest: dict[str, dict] = {}
    for decision, pattern_type in db.execute(stmt):
        if decision.symbol in latest:
            continue
        latest[decision.symbol] = {
            "decision_type": decision.decision_type,
            "status": decision.status,
            "confidence": _f(decision.confidence),
            "pattern_type": pattern_type,
            "created_at": decision.created_at.isoformat(),
        }
    return latest


def _recent_closes(db: Session, symbols: list[str], today: datetime.date) -> dict[str, dict]:
    """Dernière clôture et clôture d'il y a `WEEK_SESSIONS` séances, en une
    seule requête (pas 40 chargements d'historique complet)."""
    since = datetime.datetime.combine(today - datetime.timedelta(days=PRICE_LOOKBACK_DAYS), datetime.time.min)
    stmt = (
        select(PriceHistoryLong.symbol, PriceHistoryLong.ts, PriceHistoryLong.close)
        .where(PriceHistoryLong.symbol.in_(symbols), PriceHistoryLong.ts >= since)
        .order_by(PriceHistoryLong.symbol, PriceHistoryLong.ts)
    )
    series: dict[str, list[tuple[datetime.datetime, float]]] = {}
    for symbol, ts, close in db.execute(stmt):
        if close is None:
            continue
        series.setdefault(symbol, []).append((ts, float(close)))
    result: dict[str, dict] = {}
    for symbol, points in series.items():
        last_ts, last_close = points[-1]
        week = points[-1 - WEEK_SESSIONS][1] if len(points) > WEEK_SESSIONS else None
        result[symbol] = {
            "close": last_close,
            "as_of": last_ts.date().isoformat(),
            "week_change_pct": None if not week else round((last_close / week - 1) * 100, 2),
        }
    # Clôtures périmées (flux arrêté) : gardées pour l'affichage et la
    # valorisation, mais marquées pour ne jamais servir de prix d'exécution.
    reference = max((datetime.date.fromisoformat(p["as_of"]) for p in result.values()), default=None)
    for p in result.values():
        p["stale"] = reference is not None and (reference - datetime.date.fromisoformat(p["as_of"])).days > STALE_PRICE_DAYS
    return result


def _last_known_closes(db: Session, symbols: list[str]) -> dict[str, dict]:
    """Dernière clôture connue, à n'importe quelle date, pour des valeurs
    détenues absentes de la fenêtre récente — sert seulement à valoriser."""
    if not symbols:
        return {}
    latest = (
        select(PriceHistoryLong.symbol, func.max(PriceHistoryLong.ts).label("ts"))
        .where(PriceHistoryLong.symbol.in_(symbols), PriceHistoryLong.close.is_not(None))
        .group_by(PriceHistoryLong.symbol)
        .subquery()
    )
    stmt = select(PriceHistoryLong.symbol, PriceHistoryLong.ts, PriceHistoryLong.close).join(
        latest, (PriceHistoryLong.symbol == latest.c.symbol) & (PriceHistoryLong.ts == latest.c.ts)
    )
    return {
        symbol: {"close": float(close), "as_of": ts.date().isoformat(), "week_change_pct": None, "stale": True}
        for symbol, ts, close in db.execute(stmt)
    }


def _latest_energy(db: Session) -> list[dict]:
    stmt = (
        select(EnergyPriceSnapshot)
        .where(EnergyPriceSnapshot.commodity_code.in_(ENERGY_CODES))
        .distinct(EnergyPriceSnapshot.commodity_code)
        .order_by(EnergyPriceSnapshot.commodity_code, EnergyPriceSnapshot.snapshot_date.desc())
    )
    return [
        {
            "code": row.commodity_code,
            "price": _f(row.price),
            "unit": row.unit,
            "currency": row.currency,
            "change_24h_pct": _f(row.change_24h_pct),
            "as_of": row.snapshot_date.isoformat(),
        }
        for row in db.execute(stmt).scalars()
    ]


def _france_geopolitics(db: Session, limit: int = 3) -> list[dict]:
    stmt = (
        select(GeopoliticalKnowledge)
        .where(GeopoliticalKnowledge.country == "France")
        .order_by(GeopoliticalKnowledge.created_at.desc())
        .limit(limit)
    )
    return [
        {"date": row.created_at.date().isoformat(), "contenu": row.content, "source": row.source_url or row.source_name}
        for row in db.execute(stmt).scalars()
    ]


def _trade_history(db: Session) -> list[dict]:
    stmt = select(VirtualPortfolioTrade).order_by(VirtualPortfolioTrade.executed_at, VirtualPortfolioTrade.id)
    return [
        {"symbol": t.symbol, "side": t.side, "quantity": t.quantity, "price": float(t.price), "fees": float(t.fees)}
        for t in db.execute(stmt).scalars()
    ]


def _previous_snapshot(db: Session) -> dict | None:
    stmt = select(VirtualPortfolioSnapshot).order_by(VirtualPortfolioSnapshot.valued_at.desc()).limit(1)
    snap = db.execute(stmt).scalars().first()
    if snap is None:
        return None
    return {"report_id": snap.report_id, "valued_at": snap.valued_at.isoformat(), "total_value": float(snap.total_value)}


def _trade_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(VirtualPortfolioTrade)) or 0


def gather_db_context(db: Session, today: datetime.date) -> dict:
    securities = _cac40_securities(db)
    symbols = [s.symbol for s in securities]
    trades = _trade_history(db)
    prices = _recent_closes(db, symbols, today) if symbols else {}
    held = vp.holdings_from_trades(trades).positions
    missing_held = [symbol for symbol in held if symbol not in prices]
    return {
        "securities": [{"symbol": s.symbol, "name": s.name, "sector": s.sector} for s in securities],
        "decisions": _latest_decisions(db, symbols) if symbols else {},
        "prices": prices,
        "fallback_prices": _last_known_closes(db, missing_held),
        "bonds": build_dashboard_summary(db),
        "energy": _latest_energy(db),
        "geopolitics_france": _france_geopolitics(db),
        "trades": trades,
        "previous_snapshot": _previous_snapshot(db),
    }


# ------------------------------------------------------------- collecte réseau


def fetch_cac40_index() -> dict | None:
    """Clôture du CAC 40 et variation sur 5 séances via yfinance. `None` en cas
    d'échec : le rapport l'affiche comme indisponible plutôt que d'inventer."""
    try:
        import yfinance as yf

        history = yf.Ticker(CAC40_INDEX_TICKER).history(period="1mo", interval="1d", auto_adjust=False)
        closes = history["Close"].dropna()
        if closes.empty:
            return None
        last = float(closes.iloc[-1])
        week = float(closes.iloc[-1 - WEEK_SESSIONS]) if len(closes) > WEEK_SESSIONS else None
        return {
            "close": round(last, 2),
            "as_of": closes.index[-1].date().isoformat(),
            "week_change_pct": None if not week else round((last / week - 1) * 100, 2),
            "source": "Yahoo Finance (^FCHI)",
        }
    except Exception as exc:  # noqa: BLE001 - réseau/yfinance : dégrade vers "indisponible"
        logger.warning("Clôture du CAC 40 indisponible : %s", exc)
        return None


def fetch_web_sources() -> list[dict]:
    """Extraits web numérotés `n` (1, 2, …), dédupliqués par URL. Une requête
    en échec est ignorée, jamais bloquante."""
    sources: list[dict] = []
    seen: set[str] = set()
    for theme, query in WEB_QUERIES:
        try:
            results = web_search.search(query, max_results=WEB_RESULTS_PER_QUERY, days=WEB_NEWS_DAYS)
        except WebSearchUnavailableError as exc:
            logger.warning("Recherche web « %s » indisponible : %s", theme, exc)
            continue
        for item in results:
            url = item.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "n": len(sources) + 1,
                    "theme": theme,
                    "titre": item.get("titre") or url,
                    "url": url,
                    "extrait": (item.get("extrait") or "")[:WEB_EXTRACT_MAX_CHARS],
                }
            )
    return sources


# ------------------------------------------------------------------- calculs


def _card(bonds: dict, instrument: str) -> dict | None:
    for card in bonds.get("cards", []):
        if card.get("instrument") == instrument:
            return card
    return None


def compute_risk(bonds: dict) -> dict:
    oat = _card(bonds, BOND_INSTRUMENT_OAT_FR_10Y)
    oat_value = oat.get("value_pct") if oat else None
    spread = bonds.get("spread_oat_bund_bps")
    return {
        "level": bond_risk_level(oat_value, spread),
        "oat_10y_pct": oat_value,
        "oat_observed_at": oat.get("observed_at") if oat else None,
        "bund_10y_pct": (_card(bonds, BOND_INSTRUMENT_BUND_DE_10Y) or {}).get("value_pct"),
        "spread_oat_bund_bps": spread,
        "criteria": risk_criteria(),
    }


def decision_label(decision: dict | None) -> str | None:
    """Libellé de la décision George d'une valeur : le type de décision tant
    qu'elle est ouverte, « Sortie proposée » / « Clôturée » sinon."""
    if not decision:
        return None
    return EXIT_STATUS_LABELS.get(decision.get("status"), decision.get("decision_type"))


def build_signals(decisions: dict[str, dict]) -> dict[str, vp.Signal]:
    """Une sortie proposée ou une décision clôturée a un libellé hors de
    Achat/Renforcer/Surveiller : `virtual_portfolio.signal_kind` la lit donc
    comme baissière (vente si la valeur est détenue, jamais d'achat)."""
    signals = {}
    for symbol, d in decisions.items():
        label = decision_label(d)
        if label:
            signals[symbol] = vp.Signal(symbol, label, d.get("confidence") or 0.0)
    return signals


def build_portfolio(context: dict, risk_level: str) -> tuple[list[vp.PlannedTrade], dict]:
    """Ordres de la semaine + état du portefeuille après ces ordres."""
    known = {**context.get("fallback_prices", {}), **context["prices"]}
    tradable = {symbol: p["close"] for symbol, p in known.items() if not p.get("stale")}
    prices = {symbol: p["close"] for symbol, p in known.items()}  # valorisation
    before = vp.holdings_from_trades(context["trades"])
    planned = vp.plan_trades(
        before, build_signals(context["decisions"]), tradable, risk_level, valuation_prices=prices
    )
    after = vp.holdings_from_trades(
        context["trades"]
        + [{"symbol": t.symbol, "side": t.side, "quantity": t.quantity, "price": t.price, "fees": t.fees} for t in planned]
    )
    positions_value = vp.positions_value(after.positions, prices)
    total_value = None if positions_value is None else round(after.cash + positions_value, 2)
    previous = context.get("previous_snapshot") or {}
    previous_total = previous.get("total_value")
    names = {s["symbol"]: s["name"] for s in context["securities"]}
    summary = {
        "initial_capital": vp.INITIAL_CAPITAL,
        "fee_rate": vp.FEE_RATE,
        "min_cash_ratio": vp.MIN_CASH_BY_RISK.get(risk_level, vp.MIN_CASH_BY_RISK["indetermine"]),
        "cash": after.cash,
        "positions_value": positions_value,
        "total_value": total_value,
        "fees_total": after.fees_total,
        "performance_since_start_pct": None
        if total_value is None
        else round((total_value / vp.INITIAL_CAPITAL - 1) * 100, 2),
        "previous_total_value": previous_total,
        "previous_valued_at": previous.get("valued_at"),
        "previous_report_id": previous.get("report_id"),
        "performance_since_previous_pct": None
        if total_value is None or not previous_total
        else round((total_value / previous_total - 1) * 100, 2),
        "positions": [
            {
                "symbol": symbol,
                "name": names.get(symbol, symbol),
                "quantity": quantity,
                "price": prices.get(symbol),
                "price_as_of": (known.get(symbol) or {}).get("as_of"),
                "price_stale": bool((known.get(symbol) or {}).get("stale")),
                "value": None if prices.get(symbol) is None else round(quantity * prices[symbol], 2),
                "weight_pct": None
                if prices.get(symbol) is None or not total_value
                else round(quantity * prices[symbol] / total_value * 100, 2),
            }
            for symbol, quantity in sorted(after.positions.items())
        ],
        "trades": [
            {
                "symbol": t.symbol,
                "name": names.get(t.symbol, t.symbol),
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "gross": round(t.gross, 2),
                "fees": t.fees,
                "rationale": t.rationale,
            }
            for t in planned
        ],
    }
    return planned, summary


def build_cac40_table(context: dict, portfolio: dict) -> list[dict]:
    held = {p["symbol"]: p["quantity"] for p in portfolio["positions"]}
    traded = {t["symbol"]: t for t in portfolio["trades"]}
    rows = []
    for sec in context["securities"]:
        symbol = sec["symbol"]
        decision = context["decisions"].get(symbol) or {}
        price = context["prices"].get(symbol) or {}
        trade = traded.get(symbol)
        if trade:
            action = f"{'Achat' if trade['side'] == 'achat' else 'Vente'} simulé(e) : {trade['quantity']}"
        elif symbol in held:
            action = f"Détenu : {held[symbol]}"
        else:
            action = None
        rows.append(
            {
                "symbol": symbol,
                "name": sec["name"],
                "sector": sec["sector"],
                "close": price.get("close"),
                "week_change_pct": price.get("week_change_pct"),
                "decision_type": decision_label(decision),
                "confidence": decision.get("confidence"),
                "pattern_type": decision.get("pattern_type"),
                "portfolio_action": action,
            }
        )
    return rows


def build_llm_context(data: dict) -> dict:
    """Sous-ensemble envoyé au LLM : tout ce qu'il a le droit de citer."""
    table = data["cac40"]
    by_decision: dict[str, list[str]] = {}
    for row in table:
        by_decision.setdefault(row["decision_type"] or "Aucune décision ouverte", []).append(row["name"])
    movers = sorted((r for r in table if r["week_change_pct"] is not None), key=lambda r: r["week_change_pct"])
    return {
        "date_du_rapport": data["report_date"],
        "indicateur_risque_obligataire": data["risk"],
        "obligations": data["bonds"],
        "energie": data["energy"],
        "indice_cac40": data["cac40_index"],
        "decisions_george_par_type": by_decision,
        "plus_fortes_baisses_5_seances": [{"valeur": r["name"], "variation_pct": r["week_change_pct"]} for r in movers[:5]],
        "plus_fortes_hausses_5_seances": [
            {"valeur": r["name"], "variation_pct": r["week_change_pct"]} for r in reversed(movers[-5:])
        ],
        "portefeuille_virtuel": {k: v for k, v in data["portfolio"].items() if k != "positions"}
        | {"nombre_de_positions": len(data["portfolio"]["positions"])},
        "notes_geopolitiques_france": data["geopolitics_france"],
        "sources_web": data["sources"],
    }


FALLBACK_NARRATIVE = (
    "## Commentaire indisponible\n\n"
    "Le service de rédaction (Mistral) n'a pas répondu. Les données chiffrées ci-dessous "
    "(obligations, énergie, CAC 40, portefeuille virtuel) restent valables ; relance la "
    "génération plus tard pour obtenir le commentaire."
)


def write_narrative(llm_context: dict) -> tuple[str, str | None]:
    """(markdown, modèle utilisé) — jamais d'exception : un échec LLM produit
    un texte de repli explicite, les données chiffrées restent publiées."""
    try:
        text = mistral_client.complete(
            mistral_client.load_system_prompt(PROMPT_NAME),
            json.dumps(llm_context, ensure_ascii=False, default=str),
            model=mistral_client.MODEL_LARGE,
            temperature=0.2,
        )
        return text.strip(), mistral_client.MODEL_LARGE
    except mistral_client.MistralUnavailableError as exc:
        logger.warning("Rédaction du rapport stratégique indisponible : %s", exc)
        return FALLBACK_NARRATIVE, None


# ----------------------------------------------------------------- orchestration


def generate_report(session_factory, now: datetime.datetime | None = None) -> int:
    """Génère, enregistre et renvoie l'id d'un nouveau rapport. Les ordres
    simulés de la semaine sont enregistrés dans la même transaction que le
    rapport : pas de rapport sans ses ordres, ni d'ordres sans rapport."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    with session_factory() as db:
        context = gather_db_context(db, today)
    trades_seen = len(context["trades"])

    cac40_index = fetch_cac40_index()
    sources = fetch_web_sources()

    risk = compute_risk(context["bonds"])
    planned, portfolio = build_portfolio(context, risk["level"])
    data = {
        "report_date": today.isoformat(),
        "generated_at": now.isoformat(),
        "risk": risk,
        "bonds": context["bonds"],
        "energy": context["energy"],
        "cac40_index": cac40_index,
        "prices_as_of": max((p["as_of"] for p in context["prices"].values()), default=None),
        "portfolio": portfolio,
        "geopolitics_france": context["geopolitics_france"],
        "sources": sources,
    }
    data["cac40"] = build_cac40_table(context, portfolio)

    narrative, model_used = write_narrative(build_llm_context(data))

    with session_factory() as db:
        # Verrou de transaction (libéré au commit/rollback) puis contrôle que
        # personne n'a passé d'ordre depuis la lecture de l'historique : sinon
        # ce plan, calculé sur un portefeuille périmé, doublerait des achats.
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PORTFOLIO_LOCK_KEY})
        if _trade_count(db) != trades_seen:
            raise RuntimeError(
                "Le portefeuille virtuel a changé pendant la génération (une autre génération a eu lieu) : "
                "relance la génération."
            )
        report = StrategicReport(
            risk_level=risk["level"], narrative_markdown=narrative, data=data, model_used=model_used
        )
        db.add(report)
        db.flush()
        for trade in planned:
            db.add(
                VirtualPortfolioTrade(
                    report_id=report.id,
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    fees=trade.fees,
                    rationale=trade.rationale,
                    executed_at=now,
                )
            )
        if portfolio["total_value"] is not None:
            db.add(
                VirtualPortfolioSnapshot(
                    report_id=report.id,
                    valued_at=now,
                    cash=portfolio["cash"],
                    positions_value=portfolio["positions_value"],
                    total_value=portfolio["total_value"],
                    fees_total=portfolio["fees_total"],
                )
            )
        db.commit()
        return report.id


if __name__ == "__main__":
    from ingestion.db import get_session_factory

    logging.basicConfig(level=logging.INFO)
    report_id = generate_report(get_session_factory())
    print(f"Rapport stratégique n°{report_id} généré.")
