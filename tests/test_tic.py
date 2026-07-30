"""Tests du sous-agent de collecte TIC (`agents/collectors/tic.py`) —
réseau entièrement mocké. Fixture reconstruite à partir de la **vraie
réponse** de `slt_table5.txt` obtenue en direct pendant le développement
(texte tabulé, mois le plus récent en première colonne de données)."""

from agents.collectors import tic

_REAL_TSV = (
    "Table 5: Major Foreign Holders of Treasury Securities\n"
    "Holdings at end of time period\n"
    "Billions of dollars\n"
    "Link: https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt\n"
    "\n"
    "Country\t2026-05\t2026-04\t2026-03\n"
    "Japan\t1143.1\t1209.9\t1191.6\n"
    "United Kingdom\t948.6\t937.5\t927.1\n"
    "France\t393.1\t393.3\t393.0\n"
    "Ireland\tN/A\t345.3\t355.9\n"
)


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_tic_holdings_finds_france_row_and_most_recent_leftmost_column(monkeypatch):
    monkeypatch.setattr(tic.requests, "get", lambda url, timeout=None: _FakeResponse(_REAL_TSV))
    item = tic.fetch_tic_holdings("France", label="x", source_name="TIC (Trésor US)", unit="Md$")
    assert item is not None
    assert item.value == 393.1  # 1re colonne de données = mois le plus récent, pas la dernière
    assert item.observed_at == "2026-05"


def test_fetch_tic_holdings_falls_back_when_latest_cell_is_not_a_number(monkeypatch):
    # Ligne "Ireland" : cellule la plus récente "N/A" — doit avancer vers la
    # colonne suivante (mois plus ancien) plutôt que d'échouer.
    monkeypatch.setattr(tic.requests, "get", lambda url, timeout=None: _FakeResponse(_REAL_TSV))
    item = tic.fetch_tic_holdings("Ireland", label="x", source_name="TIC (Trésor US)", unit="Md$")
    assert item is not None
    assert item.value == 345.3
    assert item.observed_at == "2026-04"


def test_fetch_tic_holdings_returns_none_when_country_absent(monkeypatch):
    monkeypatch.setattr(tic.requests, "get", lambda url, timeout=None: _FakeResponse(_REAL_TSV))
    assert tic.fetch_tic_holdings("Germany", label="x", source_name="TIC (Trésor US)", unit="Md$") is None


def test_fetch_tic_holdings_returns_none_on_network_failure(monkeypatch):
    import requests

    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(tic.requests, "get", _raise)
    assert tic.fetch_tic_holdings("France", label="x", source_name="TIC (Trésor US)", unit="Md$") is None


def test_collect_donnees_tic_returns_empty_list_on_failure(monkeypatch):
    monkeypatch.setattr(tic, "fetch_tic_holdings", lambda *a, **k: None)
    assert tic.collect_donnees_tic(db=None, engine=None) == []
