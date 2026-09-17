"""Tests de `agents/geopolitical_veille.py`. `_load_countries`/
`_pick_weekly_countries` sont purs (aucune DB/réseau). `collect_geopolitical_news`
a besoin de Tavily/GDELT/Mistral réels pour tourner en production, mais est
testable en mockant `web_search.search`/`gdelt_client.search_articles`/
`mistral_client.complete` — même principe que
`tests/test_george_veille.py:test_collect_company_news_synthesizes_multiple_sources_and_uses_small_model`."""

import datetime

import agents.geopolitical_veille as geopolitical_veille
import agents.mistral_client as mistral_client
from agents import gdelt_client, web_search
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


def test_collect_geopolitical_news_merges_tavily_and_gdelt_into_one_mistral_call(monkeypatch):
    tavily_results = [{"titre": "Reuters — Iran", "extrait": "Tensions en hausse...", "url": "https://reuters.com/iran"}]
    gdelt_results = [{"titre": "Drone strike hits oil facility near Isfahan", "extrait": "", "url": "https://example.com/gdelt"}]
    monkeypatch.setattr(web_search, "search", lambda query, max_results=2: tavily_results)
    monkeypatch.setattr(gdelt_client, "search_articles", lambda country, max_records=10, timespan="7d": gdelt_results)

    captured = {}

    def fake_complete(system_prompt, user_message, model=None, **kwargs):
        captured["model"] = model
        captured["user_message"] = user_message
        return "Tensions confirmées par deux sources indépendantes."

    monkeypatch.setattr(mistral_client, "complete", fake_complete)

    entry = type("FakeEntry", (), {"id": 1, "created_at": datetime.datetime(2026, 9, 17, tzinfo=datetime.timezone.utc)})()
    monkeypatch.setattr(
        geopolitical_veille.geopolitical_knowledge,
        "add_geopolitical_knowledge",
        lambda db, content, country, region=None, source_name="", source_url=None: entry,
    )

    groups = geopolitical_veille.collect_geopolitical_news(db=None, engine=None, scope={"country": "Iran"})

    assert captured["model"] == mistral_client.MODEL_SMALL
    assert "Reuters" in captured["user_message"]
    assert "Drone strike hits oil facility near Isfahan" in captured["user_message"]

    label, items = groups[0]
    assert "ajoutée à geopolitical_knowledge" in label
    assert "GDELT" in items[0].source_name
    assert "2 sources" in items[0].source_name


def test_collect_geopolitical_news_returns_empty_group_when_both_sources_are_empty(monkeypatch):
    monkeypatch.setattr(web_search, "search", lambda query, max_results=2: [])
    monkeypatch.setattr(gdelt_client, "search_articles", lambda country, max_records=10, timespan="7d": [])

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Mistral ne doit pas être appelé sans aucune source.")

    monkeypatch.setattr(mistral_client, "complete", _fail_if_called)

    groups = geopolitical_veille.collect_geopolitical_news(db=None, engine=None, scope={"country": "Islande"})
    assert groups == []


def test_collect_geopolitical_news_source_name_omits_gdelt_when_gdelt_found_nothing(monkeypatch):
    """`source_name` ne doit mentionner GDELT que s'il a effectivement
    contribué des résultats -- sinon il mentirait sur la provenance."""
    tavily_results = [{"titre": "Reuters — France", "extrait": "...", "url": "https://reuters.com/france"}]
    monkeypatch.setattr(web_search, "search", lambda query, max_results=2: tavily_results)
    monkeypatch.setattr(gdelt_client, "search_articles", lambda country, max_records=10, timespan="7d": [])
    monkeypatch.setattr(mistral_client, "complete", lambda system_prompt, user_message, model=None, **kwargs: "Résumé.")

    entry = type("FakeEntry", (), {"id": 1, "created_at": datetime.datetime(2026, 9, 17, tzinfo=datetime.timezone.utc)})()
    monkeypatch.setattr(
        geopolitical_veille.geopolitical_knowledge,
        "add_geopolitical_knowledge",
        lambda db, content, country, region=None, source_name="", source_url=None: entry,
    )

    groups = geopolitical_veille.collect_geopolitical_news(db=None, engine=None, scope={"country": "France"})

    _, items = groups[0]
    assert "GDELT" not in items[0].source_name
    assert "1 sources" in items[0].source_name


def test_collect_geopolitical_news_falls_back_to_gdelt_when_tavily_is_unavailable(monkeypatch):
    """Une panne Tavily (`WebSearchUnavailableError`) ne doit jamais faire
    remonter d'exception -- dégradation vers GDELT seul, comme le documente
    la docstring de `collect_geopolitical_news`."""

    def _raise(*args, **kwargs):
        raise web_search.WebSearchUnavailableError("Tavily indisponible : boom")

    monkeypatch.setattr(web_search, "search", _raise)
    gdelt_results = [{"titre": "GDELT only", "extrait": "", "url": "https://example.com/gdelt-only"}]
    monkeypatch.setattr(gdelt_client, "search_articles", lambda country, max_records=10, timespan="7d": gdelt_results)
    monkeypatch.setattr(mistral_client, "complete", lambda system_prompt, user_message, model=None, **kwargs: "Résumé GDELT seul.")

    entry = type("FakeEntry", (), {"id": 1, "created_at": datetime.datetime(2026, 9, 17, tzinfo=datetime.timezone.utc)})()
    monkeypatch.setattr(
        geopolitical_veille.geopolitical_knowledge,
        "add_geopolitical_knowledge",
        lambda db, content, country, region=None, source_name="", source_url=None: entry,
    )

    groups = geopolitical_veille.collect_geopolitical_news(db=None, engine=None, scope={"country": "Iran"})

    _, items = groups[0]
    assert "GDELT" in items[0].source_name
    assert "1 sources" in items[0].source_name
