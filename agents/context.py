"""Constructeurs de contexte structuré pour les appels LLM de George (Phase 4)
— pur, sans accès DB, sur le même principe que `engine/backtest.py` vis-à-vis
de `engine/build_training_set.py` : ces fonctions prennent des objets déjà
récupérés (ORM ou valeurs simples) et rendent un dict JSON-sérialisable,
jamais de requête SQL ici. C'est ce dict, et rien d'autre, qui est envoyé au
LLM en message utilisateur — le prompt système interdit d'utiliser un chiffre
absent de ce contexte, donc tout ce qui doit être citable doit y figurer.

`Numeric` (SQLAlchemy) revient en `decimal.Decimal` : converti en `float` ici
pour que le contexte soit directement sérialisable en JSON.
"""
from __future__ import annotations

from engine.confidence import GEOMETRY_WEIGHT, MACD_WEIGHT, RSI_WEIGHT, STOCH_WEIGHT, TREND_WEIGHT, VOLUME_WEIGHT
from engine.exit_levels import fibonacci_retracement_levels
from ingestion.models import Basket, Decision, PatternDetected, Security

# Poids fixes de engine/confidence.py:confidence_score, forwardés tels quels
# (jamais recopiés à la main) pour que la section "Confidence scoring" de
# l'explication ne se désynchronise jamais d'un futur rebalancement des
# poids — même discipline anti-hallucination que le reste de ce fichier :
# aucun chiffre cité par le LLM ne doit vivre ailleurs que dans ce contexte.
# `stochastique` n'est ajoutée à `pattern["ponderations"]` que pour les
# figures en bougies japonaises (voir `decision_context` ci-dessous) — c'est
# la seule famille de détecteurs qui calcule réellement `stoch_conf`
# (`engine/patterns/candlestick.py`), donc la seule où ce poids s'applique
# vraiment (voir `engine/confidence.py:confidence_score`).
_CONFIDENCE_WEIGHTS = {
    "geometrie": GEOMETRY_WEIGHT,
    "volume": VOLUME_WEIGHT,
    "tendance": TREND_WEIGHT,
    "rsi": RSI_WEIGHT,
    "macd": MACD_WEIGHT,
}
_CANDLESTICK_PATTERN_TYPES = {
    "Bullish Doji", "Bearish Doji", "Hammer", "Hanging Man", "Inverted Hammer", "Shooting Star",
    "Bullish Engulfing", "Bearish Engulfing", "Morning Star", "Evening Star", "Dark Cloud Cover", "Piercing Line",
}

# Pour les figures de retournement dont `context` stocke déjà un creux/sommet
# absolu (voir `engine/patterns/reversal.py`), extrait (swing_low, swing_high)
# pour calculer des niveaux de Fibonacci informationnels — voir
# `engine/exit_levels.py:fibonacci_retracement_levels` pour pourquoi ceci ne
# remplace jamais take_profit/stop_loss déjà calculés. Les figures de
# continuation/breakout/bougies ne sont pas couvertes ici : leur `context` ne
# garde pas de creux/sommet absolu (continuation) ou n'a pas de "hauteur de
# figure" comparable (bougies) — voir la synthèse Kabbaj §7.5/§4.
_FIBONACCI_SWING_EXTRACTORS = {
    "Double Bottom": lambda c: (min(c["bottom_1"]["price"], c["bottom_2"]["price"]), c["resistance"]["price"]),
    "Double Top": lambda c: (c["support"]["price"], max(c["top_1"]["price"], c["top_2"]["price"])),
    "Head & Shoulders": lambda c: (c["neckline"]["price"], c["head"]["price"]),
    "Inverse Head & Shoulders": lambda c: (c["head"]["price"], c["neckline"]["price"]),
    "Cup & Handle": lambda c: (c["cup_bottom"]["price"], max(c["left_rim"]["price"], c["right_rim"]["price"])),
}


def _fibonacci_context(pattern: PatternDetected) -> dict | None:
    extractor = _FIBONACCI_SWING_EXTRACTORS.get(pattern.pattern_type)
    if extractor is None:
        return None
    try:
        swing_low, swing_high = extractor(pattern.context)
    except (KeyError, TypeError):
        return None
    if swing_low >= swing_high:
        return None
    return fibonacci_retracement_levels(swing_low, swing_high)


def decision_context(
    decision: Decision,
    pattern: PatternDetected | None,
    security: Security,
    jane_note: str | None = None,
) -> dict:
    context: dict = {
        "titre": {
            "symbole": security.symbol,
            "nom": security.name,
            "secteur": security.sector,
        },
        "decision": {
            "type": decision.decision_type,
            "prix_entree": float(decision.entry_price),
            "take_profit": float(decision.take_profit) if decision.take_profit is not None else None,
            "stop_loss": float(decision.stop_loss) if decision.stop_loss is not None else None,
            "confiance": float(decision.confidence),
        },
        "pattern": None,
        "jane_note": jane_note,
    }
    if pattern is not None:
        # `rsi_14`/niveaux de Fibonacci sont ajoutés après lecture de
        # George_AnalyseTechnique_Kabbaj_Synthese.md — champs choisis
        # explicitement (pas un passthrough brut de `pattern.context`, qui
        # contient aussi des index/prix internes non pertinents pour
        # l'explication) plutôt qu'un dict entier non filtré. `macd_line`/
        # `niveaux_bollinger` suivent le même principe ; `niveaux_bollinger`
        # est déjà calculé et stocké par `engine/run_detection.py:run` (pas
        # recalculé ici, aucune figure ne garde l'historique de prix complet
        # dans `context` — voir `engine/exit_levels.py:bollinger_band_levels`).
        pattern_ctx = pattern.context or {}
        # `stochastique` n'existe dans `context` que pour les figures en
        # bougies japonaises (`engine/patterns/candlestick.py`) — absent
        # (`None`) pour les 13 figures chartistes, jamais inventé.
        is_candlestick = pattern.pattern_type in _CANDLESTICK_PATTERN_TYPES
        weights = {**_CONFIDENCE_WEIGHTS, "stochastique": STOCH_WEIGHT} if is_candlestick else _CONFIDENCE_WEIGHTS
        context["pattern"] = {
            "type": pattern.pattern_type,
            "detecte_le": pattern.detected_at.isoformat(),
            "confiance": float(pattern.confidence),
            "rsi_14": pattern_ctx.get("rsi_14"),
            "macd_line": pattern_ctx.get("macd_line"),
            "niveaux_fibonacci": _fibonacci_context(pattern),
            "niveaux_bollinger": pattern_ctx.get("niveaux_bollinger"),
            # Sous-scores réels (0-1) qui composent la confiance finale
            # ci-dessus, demandés par l'utilisateur pour que la section
            # "Confidence scoring" cite les vrais chiffres calculés pour
            # CETTE figure plutôt que de reformuler la confiance globale.
            # `None` pour une figure détectée avant cet ajout (`context` n'a
            # pas encore ces clés) — jamais inventé, même logique que
            # `rsi_14` ci-dessus.
            "scores": {
                "geometrie": pattern_ctx.get("geometry_quality"),
                "volume": pattern_ctx.get("volume_confirmation"),
                "tendance": pattern_ctx.get("trend_alignment"),
                "rsi": pattern_ctx.get("rsi_confirmation"),
                "macd": pattern_ctx.get("macd_confirmation"),
                "stochastique": pattern_ctx.get("stochastic_confirmation"),
            },
            "ponderations": weights,
            # "heuristique" : `confiance` ci-dessus EST la somme pondérée des
            # 4 scores par `ponderations` (engine.confidence.confidence_score).
            # "modele_appris" : `confiance` vient du modèle XGBoost entraîné
            # (engine/scoring.py) — un modèle appris sur l'historique complet
            # peut corriger l'heuristique, pas seulement la confirmer, donc
            # `confiance` peut diverger nettement de cette somme pondérée.
            # `None` pour une figure détectée avant l'ajout de ce champ.
            "source_confiance": pattern_ctx.get("confidence_source"),
        }
    return context


def security_snapshot(
    security: Security,
    latest_decision: Decision | None,
    latest_pattern: PatternDetected | None,
) -> dict:
    """Instantané d'un titre pour le RAG SQL simple de `/chat` (tâche 3) —
    une entrée par titre reconnu dans la question posée."""
    snapshot: dict = {
        "symbole": security.symbol,
        "nom": security.name,
        "secteur": security.sector,
        "derniere_decision": None,
        "derniere_figure": None,
    }
    if latest_decision is not None:
        snapshot["derniere_decision"] = {
            "type": latest_decision.decision_type,
            "prix_entree": float(latest_decision.entry_price),
            "take_profit": float(latest_decision.take_profit) if latest_decision.take_profit is not None else None,
            "stop_loss": float(latest_decision.stop_loss) if latest_decision.stop_loss is not None else None,
            "confiance": float(latest_decision.confidence),
        }
    if latest_pattern is not None:
        snapshot["derniere_figure"] = {
            "type": latest_pattern.pattern_type,
            "detecte_le": latest_pattern.detected_at.isoformat(),
            "confiance": float(latest_pattern.confidence),
        }
    return snapshot


def exit_scenario_context(
    decision: Decision,
    security: Security,
    result: str,
    pnl_pct: float,
    scenario: str,
    volume_confirmed: bool | None,
) -> dict:
    """Contexte pour `agents/explainer.py:explain_exit_scenario` (Phase 6,
    tâche 4) — `result`/`scenario`/`volume_confirmed` viennent déjà décidés
    par `engine.exit_scenarios.classify_exit`, jamais recalculés ici ou par
    le LLM : ce module ne fait que les mettre en mots."""
    return {
        "titre": {"symbole": security.symbol, "nom": security.name},
        "decision": {
            "type": decision.decision_type,
            "prix_entree": float(decision.entry_price),
            "take_profit": float(decision.take_profit) if decision.take_profit is not None else None,
            "stop_loss": float(decision.stop_loss) if decision.stop_loss is not None else None,
        },
        "resultat": result,
        "pnl_pct": round(pnl_pct, 2),
        "scenario_propose": scenario,
        "confirme_par_volume": volume_confirmed,
    }


def carry_trade_context(scored_pair: dict) -> dict:
    """Contexte pour `agents/explainer.py:explain_carry_trade` (ad hoc, pas
    une phase du roadmap) — `scored_pair` est déjà le dict complet renvoyé
    par `engine.carry_index.compute_carry_score` (+ métadonnées de la
    paire), jamais recalculé ici. Retranscrit tel quel plutôt que
    reconstruit à la main, pour qu'aucun chiffre affiché ne diffère de ceux
    passés au LLM."""
    return {
        "paire": {
            "symbole": scored_pair["symbol"],
            "nom": scored_pair["name"],
            "devise_financement": scored_pair["funding_currency"],
            "devise_cible": scored_pair["target_currency"],
        },
        "taux": {
            "financement_pct": scored_pair["funding_rate_pct"],
            "cible_pct": scored_pair["target_rate_pct"],
        },
        "score": {
            "differentiel_carry_pct": scored_pair["carry_pct"],
            "volatilite_realisee_pct": scored_pair["realized_vol_pct"],
            "ratio_carry_vol": scored_pair["carry_vol_ratio"],
            "score_saturation_cot": scored_pair["cot_crowding_score"],
        },
        "decision": scored_pair["decision"],
    }


def basket_report_context(
    basket: Basket | None,
    george_index: float | None,
    decisions: list[Decision],
    security_count: int,
) -> dict:
    """`basket=None` désigne un rapport portefeuille (tous les paniers), pas
    un panier particulier — voir `agents/reports.py:generate_report`."""
    return {
        "perimetre": {"type": "panier", "nom": basket.name} if basket is not None else {"type": "portefeuille"},
        "nombre_titres": security_count,
        "george_index": george_index,
        "decisions_actives": [
            {
                "symbole": d.symbol,
                "type": d.decision_type,
                "confiance": float(d.confidence),
            }
            for d in decisions
        ],
    }
