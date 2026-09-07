"""Tests de `agents/context.py` — pur, sans DB, sans réseau (Phase 4). Ces
constructeurs de contexte sont ce qui est envoyé au LLM en message
utilisateur : vérifier qu'ils reprennent fidèlement les valeurs numériques
réelles est la première moitié de la garantie anti-invention (l'autre
moitié — que la réponse du LLM les cite bien — est testée dans
`tests/test_api.py` avec un client Mistral factice)."""
import datetime

from agents.chat import _find_biofuel_company, _format_opportunities, _requested_decision_type
from agents.context import basket_report_context, decision_context, security_snapshot
from ingestion.models import Basket, Decision, PatternDetected, Security


def _security(symbol="AIR.PA"):
    return Security(symbol=symbol, name="Airbus", country="FR", currency="EUR", sector="Aéronautique", theme=None)


def _decision(symbol="AIR.PA"):
    return Decision(
        symbol=symbol,
        decision_type="Achat",
        entry_price=129.5,
        take_profit=140.0,
        stop_loss=120.0,
        confidence=77.0,
    )


def _pattern(symbol="AIR.PA"):
    return PatternDetected(
        symbol=symbol,
        pattern_type="Bull Flag",
        detected_at=datetime.datetime(2026, 7, 20, tzinfo=datetime.timezone.utc),
        confidence=77.0,
        context={},
    )


def test_decision_context_carries_real_numbers():
    context = decision_context(_decision(), _pattern(), _security())
    assert context["decision"]["prix_entree"] == 129.5
    assert context["decision"]["take_profit"] == 140.0
    assert context["decision"]["stop_loss"] == 120.0
    assert context["decision"]["confiance"] == 77.0
    assert context["pattern"]["type"] == "Bull Flag"
    assert context["pattern"]["confiance"] == 77.0
    assert context["titre"]["symbole"] == "AIR.PA"
    assert context["jane_note"] is None


def test_decision_context_without_pattern_is_none_not_fabricated():
    context = decision_context(_decision(), None, _security())
    assert context["pattern"] is None


def test_decision_context_carries_jane_note_verbatim():
    context = decision_context(_decision(), _pattern(), _security(), jane_note="Corrélation macro à surveiller.")
    assert context["jane_note"] == "Corrélation macro à surveiller."


def test_decision_context_carries_rsi_when_present():
    pattern = _pattern()
    pattern.context = {"rsi_14": 62.3}
    context = decision_context(_decision(), pattern, _security())
    assert context["pattern"]["rsi_14"] == 62.3


def test_decision_context_rsi_is_none_when_absent_from_pattern_context():
    """Figures détectées avant l'ajout du RSI (§ synthèse Kabbaj) : `context`
    n'a pas la clé `rsi_14` — ne doit jamais planter, ni en inventer un."""
    context = decision_context(_decision(), _pattern(), _security())
    assert context["pattern"]["rsi_14"] is None


def test_decision_context_carries_confidence_subscores_when_present():
    pattern = _pattern()
    pattern.context = {
        "geometry_quality": 0.82,
        "volume_confirmation": 1.0,
        "trend_alignment": 0.5,
        "rsi_confirmation": 1.0,
        "macd_confirmation": 0.7,
    }
    context = decision_context(_decision(), pattern, _security())
    assert context["pattern"]["scores"] == {
        "geometrie": 0.82,
        "volume": 1.0,
        "tendance": 0.5,
        "rsi": 1.0,
        "macd": 0.7,
        # `_pattern()` est un "Bull Flag" (figure chartiste classique), pas
        # une bougie japonaise -- `stochastic_confirmation` n'existe donc
        # jamais dans son `context` (voir `engine/patterns/candlestick.py`).
        "stochastique": None,
    }


def test_decision_context_subscores_are_none_when_absent_from_pattern_context():
    """Même précédent que rsi_14 : une figure détectée avant l'ajout de ce
    détail n'a pas ces clés dans `context` — jamais inventé."""
    context = decision_context(_decision(), _pattern(), _security())
    assert context["pattern"]["scores"] == {
        "geometrie": None,
        "volume": None,
        "tendance": None,
        "rsi": None,
        "macd": None,
        "stochastique": None,
    }


def test_decision_context_carries_confidence_source_when_present():
    pattern = _pattern()
    pattern.context = {"confidence_source": "modele_appris"}
    context = decision_context(_decision(), pattern, _security())
    assert context["pattern"]["source_confiance"] == "modele_appris"


def test_decision_context_confidence_source_is_none_when_absent_from_pattern_context():
    context = decision_context(_decision(), _pattern(), _security())
    assert context["pattern"]["source_confiance"] is None


def test_decision_context_always_carries_the_real_confidence_weights():
    """Les pondérations sont des constantes globales de engine.confidence,
    pas propres à une figure -- toujours présentes, forwardées depuis la
    source plutôt que recopiées à la main pour ne jamais se désynchroniser
    d'un futur rebalancement."""
    from engine.confidence import GEOMETRY_WEIGHT, MACD_WEIGHT, RSI_WEIGHT, TREND_WEIGHT, VOLUME_WEIGHT

    # `_pattern()` est un "Bull Flag" -- pas de clé "stochastique" ici, voir
    # `test_decision_context_carries_the_stochastic_weight_for_candlesticks`.
    context = decision_context(_decision(), _pattern(), _security())
    assert context["pattern"]["ponderations"] == {
        "geometrie": GEOMETRY_WEIGHT,
        "volume": VOLUME_WEIGHT,
        "tendance": TREND_WEIGHT,
        "rsi": RSI_WEIGHT,
        "macd": MACD_WEIGHT,
    }


def test_decision_context_carries_the_stochastic_weight_for_candlesticks():
    """Le stochastique n'est documenté (synthèse Kabbaj §2.7/§4) qu'en
    combinaison avec les bougies japonaises -- son poids n'apparaît donc dans
    `ponderations` que pour ces 12 types de figures, jamais pour les 13
    figures chartistes classiques (voir le test ci-dessus)."""
    from engine.confidence import STOCH_WEIGHT

    pattern = _pattern()
    pattern.pattern_type = "Hammer"
    context = decision_context(_decision(), pattern, _security())
    assert context["pattern"]["ponderations"]["stochastique"] == STOCH_WEIGHT


def test_decision_context_computes_fibonacci_levels_for_reversal_pattern():
    pattern = PatternDetected(
        symbol="AIR.PA",
        pattern_type="Double Bottom",
        detected_at=datetime.datetime(2026, 7, 20, tzinfo=datetime.timezone.utc),
        confidence=77.0,
        context={
            "bottom_1": {"index": 1, "price": 90.0},
            "bottom_2": {"index": 10, "price": 91.0},
            "resistance": {"index": 5, "price": 110.0},
        },
    )
    context = decision_context(_decision(), pattern, _security())
    levels = context["pattern"]["niveaux_fibonacci"]
    assert levels is not None
    assert set(levels) == {"38.2%", "50.0%", "61.8%", "76.4%"}


def test_decision_context_fibonacci_is_none_for_pattern_without_absolute_swing():
    """Bull Flag (comme les autres figures de continuation/bougies) n'a pas
    de creux/sommet absolu dans son `context` — jamais de niveaux inventés."""
    context = decision_context(_decision(), _pattern(), _security())
    assert context["pattern"]["niveaux_fibonacci"] is None


def test_security_snapshot_with_no_decision_or_pattern_stays_none():
    snapshot = security_snapshot(_security(), None, None)
    assert snapshot["derniere_decision"] is None
    assert snapshot["derniere_figure"] is None
    assert snapshot["symbole"] == "AIR.PA"


def test_security_snapshot_carries_real_numbers():
    snapshot = security_snapshot(_security(), _decision(), _pattern())
    assert snapshot["derniere_decision"]["prix_entree"] == 129.5
    assert snapshot["derniere_figure"]["type"] == "Bull Flag"


def test_basket_report_context_portfolio_scope_has_no_george_index():
    context = basket_report_context(None, None, [_decision()], 12)
    assert context["perimetre"] == {"type": "portefeuille"}
    assert context["nombre_titres"] == 12
    assert context["george_index"] is None
    assert context["decisions_actives"][0]["symbole"] == "AIR.PA"


def test_basket_report_context_basket_scope_carries_george_index():
    basket = Basket(id=1, name="Tech FR", type="secteur")
    context = basket_report_context(basket, 64.2, [], 3)
    assert context["perimetre"] == {"type": "panier", "nom": "Tech FR"}
    assert context["george_index"] == 64.2


def test_requested_decision_type_recognizes_keywords():
    assert _requested_decision_type("Quelles sont les opportunités d'achat ?") == "Achat"
    assert _requested_decision_type("Que dois-je surveiller ?") == "Surveiller"
    assert _requested_decision_type("Quel est le temps à Paris ?") is None


def test_format_opportunities_lists_every_entry_with_real_numbers():
    decisions = [
        {"symbole": "AAA.PA", "type": "Achat", "statut": "proposee", "confiance": 85.0, "prix_entree": 100.0, "take_profit": 110.0, "stop_loss": 95.0},
        {"symbole": "BBB.PA", "type": "Achat", "statut": "confirmee", "confiance": 70.0, "prix_entree": 50.0, "take_profit": None, "stop_loss": None},
    ]
    text = _format_opportunities(decisions, "Achat")
    assert "AAA.PA" in text and "BBB.PA" in text  # aucune entrée omise
    assert "85.0" in text and "70.0" in text
    assert "110.00" in text and "95.00" in text


def test_format_opportunities_empty_says_so_without_inventing():
    text = _format_opportunities([], "Renforcer")
    assert "renforcer" in text.lower()
    assert "aucune décision" in text.lower()


def test_find_biofuel_company_matches_a_known_name():
    assert _find_biofuel_company("Que penses-tu de Neste en ce moment ?") == "Neste"
    assert _find_biofuel_company("Actualités sur Waga Energy ?") == "Waga Energy"


def test_find_biofuel_company_returns_none_when_no_match():
    assert _find_biofuel_company("Que penses-tu d'Apple ?") is None
    assert _find_biofuel_company("Quelles sont les opportunités d'achat ?") is None
