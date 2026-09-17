"""Tests de `agents/geopolitical_veille.py`. `_load_countries`/
`_pick_weekly_countries` sont purs (aucune DB/réseau) — contrairement à
`collect_geopolitical_news`, qui a besoin de Tavily/Mistral réels et n'est
donc pas testé unitairement ici (même tiering que
`agents/george_veille.py`/`tests/test_george_veille.py`)."""

import datetime

import agents.geopolitical_veille as geopolitical_veille
from agents.geopolitical_veille import COUNTRIES_PER_RUN, _load_countries, _pick_weekly_countries


def test_load_countries_reads_the_real_whitelist():
    """`whitelist_journaux.json` doit rester chargeable tel quel — si ce
    test casse après une édition du fichier, la structure attendue
    (country/language/outlets/sites) a probablement été rompue."""
    countries = _load_countries()
    assert len(countries) == 77
    names = {c["country"] for c in countries}
    assert "France" in names
    assert "États-Unis" in names
    sample = next(c for c in countries if c["country"] == "France")
    assert sample["language"]
    assert isinstance(sample["outlets"], list) and sample["outlets"]
    assert isinstance(sample["sites"], list) and sample["sites"]


def test_pick_weekly_countries_returns_the_requested_count():
    countries = [{"country": f"Pays {i}"} for i in range(20)]
    picked = _pick_weekly_countries(countries, n=5)
    assert len(picked) == 5


def test_pick_weekly_countries_wraps_around_circularly_at_the_end_of_the_list(monkeypatch):
    """Une tranche qui déborderait la fin de la liste doit reprendre au
    début plutôt que de renvoyer moins de `n` pays -- appelle réellement
    `_pick_weekly_countries` (pas juste la formule recopiée à côté, sinon ce
    test ne détecterait jamais une régression dans le vrai code), avec une
    semaine ISO figée (`datetime.now` mocké, même principe que
    `tests/test_george_veille.py:test_pick_daily_companies_...`) choisie
    pour que 7 pays / 5 par tranche force un vrai bouclage : semaine 1 ->
    start=(1*5)%7=5, indices [5,6,0,1,2]."""
    countries = [{"country": f"Pays {i}"} for i in range(7)]
    fixed_now = datetime.datetime(2024, 1, 4, tzinfo=datetime.timezone.utc)  # semaine ISO 1

    class _FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    original = geopolitical_veille.datetime
    geopolitical_veille.datetime = _FakeDateTime
    try:
        picked = _pick_weekly_countries(countries, n=5)
    finally:
        geopolitical_veille.datetime = original

    assert len(picked) == 5
    assert [c["country"] for c in picked] == ["Pays 5", "Pays 6", "Pays 0", "Pays 1", "Pays 2"]


def test_pick_weekly_countries_is_deterministic_within_the_same_week():
    countries = [{"country": f"Pays {i}"} for i in range(77)]
    first = _pick_weekly_countries(countries)
    second = _pick_weekly_countries(countries)
    assert first == second


def test_pick_weekly_countries_default_count_matches_the_module_constant():
    countries = [{"country": f"Pays {i}"} for i in range(77)]
    assert len(_pick_weekly_countries(countries)) == COUNTRIES_PER_RUN


def test_pick_weekly_countries_handles_fewer_countries_than_requested():
    countries = [{"country": "Seul pays"}]
    picked = _pick_weekly_countries(countries, n=8)
    assert len(picked) == 1


def test_pick_weekly_countries_returns_empty_list_for_no_countries():
    assert _pick_weekly_countries([], n=8) == []
