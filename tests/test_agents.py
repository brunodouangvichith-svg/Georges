"""Tests de `agents/context.py` — pur, sans DB, sans réseau (Phase 4). Ces
constructeurs de contexte sont ce qui est envoyé au LLM en message
utilisateur : vérifier qu'ils reprennent fidèlement les valeurs numériques
réelles est la première moitié de la garantie anti-invention (l'autre
moitié — que la réponse du LLM les cite bien — est testée dans
`tests/test_api.py` avec un client Mistral factice)."""
import datetime

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
