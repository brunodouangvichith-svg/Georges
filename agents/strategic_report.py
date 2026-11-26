"""Rapport stratégique hebdomadaire — France, marchés et CAC 40 (ad hoc, pas
une phase du roadmap). Demandé directement par l'utilisateur sur le modèle
d'un rapport qu'il avait obtenu ailleurs ; généré à la demande (bouton de
l'onglet « Rapport », web et mobile) via `api/routers/strategic_reports.py`.

Même contrat anti-hallucination que le reste de `agents/` :
1. **Tout ce qui est chiffré est calculé en Python** à partir de la base de
   George (rendements OAT/Bund/Treasuries et spread, Brent, décisions de
   George sur les 40 valeurs) ou d'appels déterministes
   (clôture du CAC 40 via yfinance, extraits d'articles Tavily numérotés).
   Ces données sont stockées telles quelles dans `StrategicReport.data` et
   affichées par l'interface sans passer par le LLM.
2. **Le LLM ne fait que commenter** ce contexte (`agents/prompts/
   strategic_report_system.txt`) : il ne peut citer que des chiffres présents
   dans le contexte, et doit renvoyer à la source web numérotée `[n]` pour
   tout chiffre qui vient d'un article.

Les accès réseau (Tavily, yfinance, Mistral) se font **hors de toute session
base de données** : avec un pool limité à 2 + 2 connexions
(`ingestion/db.py`), garder une connexion ouverte pendant un appel LLM d'une
minute affamerait le reste de l'API.
"""

from __future__ import annotations

import datetime
import json
import logging
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import mistral_client, web_search
from agents.web_search import WebSearchUnavailableError
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
)

logger = logging.getLogger(__name__)

CAC40_THEME = "CAC 40"
CAC40_INDEX_TICKER = "^FCHI"
# Libellé affiché pour une décision dont George a proposé ou
# confirmé la sortie : `engine/monitor_decisions.py` passe le statut à
# `sortie_proposee` sans changer `decision_type` (qui reste "Achat") — lire
# seulement `decision_type` ferait d'une sortie un achat.
EXIT_STATUS_LABELS = {"sortie_proposee": "Sortie proposée", "cloturee": "Clôturée"}
PRICE_LOOKBACK_DAYS = 20
WEEK_SESSIONS = 5
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
    """`None` pour une valeur absente **ou non finie** : yfinance écrit
    parfois des clôtures NaN dans `price_history_long` (colonne `Numeric`,
    qui accepte NaN), et un NaN fausserait les calculs puis ferait échouer
    le stockage JSONB (NaN n'est pas du JSON valide)."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _json_safe(value):
    """Remplace récursivement tout float non fini par `None` avant stockage
    dans `strategic_reports.data` (JSONB refuse NaN/Infinity)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# ---------------------------------------------------------------- collecte DB


def _cac40_securities(db: Session) -> list[Security]:
    stmt = select(Security).where(Security.theme == CAC40_THEME).order_by(Security.name)
    return list(db.execute(stmt).scalars())


def _latest_decisions(db: Session, symbols: list[str]) -> dict[str, dict]:
    """Décision la plus récente par valeur, quel que soit son statut (une
    décision clôturée ou en sortie compte), avec le
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
        close = _f(close)
        if close is None:
            continue
        series.setdefault(symbol, []).append((ts, close))
    result: dict[str, dict] = {}
    for symbol, points in series.items():
        last_ts, last_close = points[-1]
        week = points[-1 - WEEK_SESSIONS][1] if len(points) > WEEK_SESSIONS else None
        result[symbol] = {
            "close": last_close,
            "as_of": last_ts.date().isoformat(),
            "week_change_pct": None if not week else round((last_close / week - 1) * 100, 2),
        }
    return result


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


def gather_db_context(db: Session, today: datetime.date) -> dict:
    securities = _cac40_securities(db)
    symbols = [s.symbol for s in securities]
    prices = _recent_closes(db, symbols, today) if symbols else {}
    return {
        "securities": [{"symbol": s.symbol, "name": s.name, "sector": s.sector} for s in securities],
        "decisions": _latest_decisions(db, symbols) if symbols else {},
        "prices": prices,
        "bonds": build_dashboard_summary(db),
        "energy": _latest_energy(db),
        "geopolitics_france": _france_geopolitics(db),
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


def build_cac40_table(context: dict) -> list[dict]:
    rows = []
    for sec in context["securities"]:
        symbol = sec["symbol"]
        decision = context["decisions"].get(symbol) or {}
        price = context["prices"].get(symbol) or {}
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
        "notes_geopolitiques_france": data["geopolitics_france"],
        "sources_web": data["sources"],
    }


FALLBACK_NARRATIVE = (
    "## Commentaire indisponible\n\n"
    "Le service de rédaction (Mistral) n'a pas répondu. Les données chiffrées ci-dessous "
    "(obligations, énergie, CAC 40) restent valables ; relance la "
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
    """Génère, enregistre et renvoie l'id d'un nouveau rapport."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    today = now.date()

    with session_factory() as db:
        context = gather_db_context(db, today)

    cac40_index = fetch_cac40_index()
    sources = fetch_web_sources()

    risk = compute_risk(context["bonds"])
    data = {
        "report_date": today.isoformat(),
        "generated_at": now.isoformat(),
        "risk": risk,
        "bonds": context["bonds"],
        "energy": context["energy"],
        "cac40_index": cac40_index,
        "prices_as_of": max((p["as_of"] for p in context["prices"].values()), default=None),
        "geopolitics_france": context["geopolitics_france"],
        "sources": sources,
    }
    data["cac40"] = build_cac40_table(context)

    narrative, model_used = write_narrative(build_llm_context(data))

    with session_factory() as db:
        report = StrategicReport(
            risk_level=risk["level"], narrative_markdown=narrative, data=_json_safe(data), model_used=model_used
        )
        db.add(report)
        db.commit()
        return report.id


if __name__ == "__main__":
    from ingestion.db import get_session_factory

    logging.basicConfig(level=logging.INFO)
    report_id = generate_report(get_session_factory())
    print(f"Rapport stratégique n°{report_id} généré.")
