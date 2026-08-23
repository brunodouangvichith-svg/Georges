"""Tests de `agents/jane_veille.py:collect_veille_methodologique` -- réseau/
LLM et écriture en base mockés, même principe que `tests/test_collectors.py`
pour `synthesis.py` (source unique, pas de recoupement multi-source à
tester ici)."""

import base64
import datetime

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
