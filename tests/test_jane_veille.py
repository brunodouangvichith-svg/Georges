"""Tests de `agents/jane_veille.py:collect_veille_methodologique` -- réseau/
LLM et écriture en base mockés, même principe que `tests/test_collectors.py`
pour `synthesis.py` (source unique, pas de recoupement multi-source à
tester ici)."""

import base64
import datetime
import json

import pytest

import agents.jane_veille as jane_veille
import agents.mistral_client as mistral_client
from ingestion.models import JaneKnowledge

# PNG 1x1 transparent minimal, valide -- pour tester l'encodage réel en data
# URI sans dépendre d'une vraie photo.
ONE_PIXEL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_collect_veille_methodologique_requires_source_name():
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(db=None, engine=None, scope=None)
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(db=None, engine=None, scope={"content": "..."})


def test_collect_veille_methodologique_requires_exactly_one_of_content_or_image_paths():
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(db=None, engine=None, scope={"source_name": "Investopedia"})
    with pytest.raises(ValueError):
        jane_veille.collect_veille_methodologique(
            db=None,
            engine=None,
            scope={"source_name": "Investopedia", "content": "texte", "image_paths": ["diagramme.png"]},
        )


def test_encode_image_data_uri_rejects_unsupported_format(tmp_path):
    heic_path = tmp_path / "diagramme.heic"
    heic_path.write_bytes(b"peu importe le contenu, l'extension suffit a rejeter")
    with pytest.raises(ValueError, match="JPEG/PNG"):
        jane_veille._encode_image_data_uri(heic_path)


def test_encode_image_data_uri_encodes_a_real_png(tmp_path):
    png_path = tmp_path / "diagramme.png"
    png_path.write_bytes(base64.b64decode(ONE_PIXEL_PNG_BASE64))
    data_uri = jane_veille._encode_image_data_uri(png_path)
    assert data_uri.startswith("data:image/png;base64,")
    assert data_uri.endswith(ONE_PIXEL_PNG_BASE64)


def test_collect_veille_methodologique_summarizes_images_via_vision_model(tmp_path, monkeypatch):
    png_path = tmp_path / "tete_epaules.png"
    png_path.write_bytes(base64.b64decode(ONE_PIXEL_PNG_BASE64))

    captured = {}

    def fake_complete_vision(system_prompt, user_text, image_data_uris, model=None, **kwargs):
        captured["model"] = model
        captured["image_data_uris"] = image_data_uris
        return "FIGURE CANDIDATE : tête-épaules avec ligne de cou annotée."

    monkeypatch.setattr(mistral_client, "complete_vision", fake_complete_vision)
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: None)

    groups = jane_veille.collect_veille_methodologique(
        db=None,
        engine=None,
        scope={"source_name": "Galerie photo (diagrammes perso)", "image_paths": [str(png_path)]},
    )
    label, items = groups[0]
    assert items[0].value == "FIGURE CANDIDATE : tête-épaules avec ligne de cou annotée."
    # mistral-large-latest n'est pas confirmé vision -- le chemin image doit utiliser mistral-small-latest.
    assert captured["model"] == mistral_client.MODEL_SMALL
    assert len(captured["image_data_uris"]) == 1
    assert captured["image_data_uris"][0].startswith("data:image/png;base64,")


def test_collect_veille_methodologique_adds_summary_to_jane_knowledge(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Le ratio de Sharpe mesure le rendement ajusté au risque.")

    entry = JaneKnowledge(
        content="Le ratio de Sharpe mesure le rendement ajusté au risque.",
        source_name="Investopedia",
        source_url="https://www.investopedia.com/sharpe-ratio",
    )
    entry.id = 1
    entry.created_at = datetime.datetime(2026, 8, 23, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: entry)

    groups = jane_veille.collect_veille_methodologique(
        db=None,
        engine=None,
        scope={
            "source_name": "Investopedia",
            "content": "Texte brut de la page Investopedia sur le ratio de Sharpe...",
            "source_url": "https://www.investopedia.com/sharpe-ratio",
        },
    )
    assert len(groups) == 1
    label, items = groups[0]
    assert "Investopedia" in label
    assert "ajoutée à jane_knowledge" in label
    assert len(items) == 1
    assert items[0].value == "Le ratio de Sharpe mesure le rendement ajusté au risque."
    assert items[0].source_name == "Investopedia"
    assert items[0].observed_at == "2026-08-23T00:00:00+00:00"


def test_collect_veille_methodologique_reports_deduped_when_add_knowledge_skips(monkeypatch):
    monkeypatch.setattr(mistral_client, "complete", lambda *a, **k: "Résumé quasi identique à un existant.")
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: None)

    groups = jane_veille.collect_veille_methodologique(
        db=None, engine=None, scope={"source_name": "BabyPips", "content": "Texte déjà couvert par une entrée existante."}
    )
    label, items = groups[0]
    assert "quasi-doublon ignoré" in label
    # La valeur reste le résumé réel malgré le doublon -- observable dans le flux d'activité même non retenu en base.
    assert items[0].value == "Résumé quasi identique à un existant."


def test_collect_veille_methodologique_already_summarized_skips_the_llm_call(monkeypatch):
    """`already_summarized: true` -- le texte fourni est déjà la description
    finale (ex. écrite par un agent multimodal ayant lu l'image directement)
    et ne doit jamais repasser par `mistral_client.complete` (qui
    reformulerait/dériverait un contenu déjà fact-checké)."""

    def _fail_if_called(*a, **k):
        raise AssertionError("mistral_client.complete ne doit pas être appelé quand already_summarized=True")

    monkeypatch.setattr(mistral_client, "complete", _fail_if_called)
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: None)

    groups = jane_veille.collect_veille_methodologique(
        db=None,
        engine=None,
        scope={
            "source_name": "Galerie photo personnelle — Hammer",
            "content": "Description déjà rédigée, à ajouter telle quelle.",
            "already_summarized": True,
        },
    )
    label, items = groups[0]
    assert items[0].value == "Description déjà rédigée, à ajouter telle quelle."


def test_collect_veille_methodologique_already_summarized_rejects_image_paths():
    with pytest.raises(ValueError, match="already_summarized"):
        jane_veille.collect_veille_methodologique(
            db=None,
            engine=None,
            scope={"source_name": "x", "image_paths": ["diagramme.png"], "already_summarized": True},
        )


def test_collect_veille_methodologique_rejects_non_boolean_already_summarized():
    """Un fichier --batch édité à la main peut écrire par erreur la chaîne
    "false" (JSON invalide pour un booléen mais accepté comme chaîne) --
    une chaîne non vide est truthy en Python, donc sans cette validation le
    contenu brut serait silencieusement stocké non résumé."""
    with pytest.raises(ValueError, match="booléen"):
        jane_veille.collect_veille_methodologique(
            db=None,
            engine=None,
            scope={"source_name": "x", "content": "texte", "already_summarized": "false"},
        )


class _FakeBatchSession:
    """Session factice pour `_run_batch` -- utilisée comme context manager
    (`with session_factory() as db:`), et compte les appels à `rollback()`
    pour vérifier qu'une entrée en échec ne corrompt pas la session pour les
    entrées suivantes (voir docstring de `_run_batch`)."""

    def __init__(self):
        self.rollback_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def rollback(self):
        self.rollback_calls += 1


def test_run_batch_counts_added_duplicates_and_failures_and_rolls_back_on_error(tmp_path, monkeypatch, capsys):
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(
        json.dumps(
            [
                {"source_name": "A", "content": "texte A", "already_summarized": True},
                {"source_name": "B", "content": "texte B", "already_summarized": True},
                {"source_name": "C", "content": "texte C", "image_paths": ["x.png"]},  # scope ambigu -> échoue
            ]
        ),
        encoding="utf-8",
    )

    import agents.orchestrator.run as orchestrator_run
    import ingestion.db as db_module

    fake_session = _FakeBatchSession()
    monkeypatch.setattr(db_module, "get_engine", lambda: object())
    monkeypatch.setattr(db_module, "get_session_factory", lambda: (lambda: fake_session))

    def fake_run_collection_task(db, engine, task_type, collector, scope):
        # Reproduit la vraie erreur (`collect_veille_methodologique` lève ValueError
        # sur un scope content+image_paths simultanés) sans dépendre de Mistral/DB réels.
        collector(db, engine, scope)  # lève pour "C", jamais atteint pour A/B (mock direct ci-dessous)
        raise AssertionError("ne devrait pas être atteint dans ce test")

    def fake_run_collection_task_for_ab(db, engine, task_type, collector, scope):
        status = jane_veille.DUPLICATE_STATUS_NOTE if scope["source_name"] == "B" else jane_veille.ADDED_STATUS_NOTE
        event = type("FakeEvent", (), {"description": f"Veille méthodologique — {scope['source_name']} ({status})"})()
        return {"validated": [event], "quarantined_count": 0}

    def dispatch(db, engine, task_type, collector, scope):
        if scope["source_name"] == "C":
            return fake_run_collection_task(db, engine, task_type, collector, scope)
        return fake_run_collection_task_for_ab(db, engine, task_type, collector, scope)

    monkeypatch.setattr(orchestrator_run, "run_collection_task", dispatch)

    jane_veille._run_batch(str(batch_path))

    captured = capsys.readouterr()
    assert "1 entrée(s) ajoutée(s)" in captured.out
    assert "1 quasi-doublon(s) ignoré(s)" in captured.out
    assert "1 échec(s)" in captured.out


def test_run_batch_survives_a_non_dict_entry(tmp_path, monkeypatch, capsys):
    """Un fichier batch édité à la main peut contenir une entrée qui n'est
    même pas un objet JSON (ex. une chaîne isolée par erreur) -- ne doit pas
    planter avant que l'entrée fautive soit comptée comme un échec, ni
    empêcher le traitement de l'entrée valide qui suit."""
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(
        json.dumps(["oops-not-a-dict", {"source_name": "A", "content": "texte A", "already_summarized": True}]),
        encoding="utf-8",
    )

    import agents.orchestrator.run as orchestrator_run
    import ingestion.db as db_module

    fake_session = _FakeBatchSession()
    monkeypatch.setattr(db_module, "get_engine", lambda: object())
    monkeypatch.setattr(db_module, "get_session_factory", lambda: (lambda: fake_session))
    monkeypatch.setattr(jane_veille.jane_knowledge, "add_knowledge", lambda db, content, source_name, source_url=None: None)

    def fake_run_collection_task(db, engine, task_type, collector, scope):
        collector(db, engine, scope)  # lève AttributeError pour la chaîne, jamais pour le dict
        event = type("FakeEvent", (), {"description": f"Veille méthodologique — {scope['source_name']} ({jane_veille.ADDED_STATUS_NOTE})"})()
        return {"validated": [event], "quarantined_count": 0}

    monkeypatch.setattr(orchestrator_run, "run_collection_task", fake_run_collection_task)

    jane_veille._run_batch(str(batch_path))

    captured = capsys.readouterr()
    assert "1 entrée(s) ajoutée(s)" in captured.out
    assert "1 échec(s)" in captured.out
    assert fake_session.rollback_calls == 1


def test_run_batch_exits_clearly_on_malformed_json(tmp_path):
    batch_path = tmp_path / "batch.json"
    batch_path.write_text("[{\"source_name\": \"A\",]", encoding="utf-8")  # virgule finale invalide
    with pytest.raises(SystemExit, match="JSON malformé"):
        jane_veille._run_batch(str(batch_path))


def test_run_batch_exits_clearly_when_top_level_is_not_a_list(tmp_path):
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps({"source_name": "A", "content": "texte"}), encoding="utf-8")  # objet, pas une liste
    with pytest.raises(SystemExit, match="liste JSON"):
        jane_veille._run_batch(str(batch_path))


def test_run_batch_exits_clearly_on_missing_file(tmp_path):
    with pytest.raises(SystemExit, match="introuvable"):
        jane_veille._run_batch(str(tmp_path / "n-existe-pas.json"))
