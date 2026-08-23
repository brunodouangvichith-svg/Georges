"""Sous-agent de veille méthodologique de Jane (Phase 7) — résume un contenu
déjà récupéré (article, page de référence, note, ou diagramme photographié)
et l'ajoute à `jane_knowledge` (`agents/jane_knowledge.py`), pour un
enrichissement continu du savoir sur lequel s'appuie
`agents.jane.second_opinion` (voir `agents/jane.py`).

Décision de scope (MVP, même discipline que `agents/collectors/synthesis.py`
remplaçant EDGAR) : ce module ne scrape pas lui-même Investopedia/BabyPips/
TradingView/ProRealTime/NanoTrader — le roadmap (Phase 7) prévoit Playwright/
Scrapy pour ça, une dépendance non encore ajoutée au projet, et du code de
scraping non vérifié en direct contre ces sites précis serait plus
susceptible de casser silencieusement que d'apporter une vraie valeur (voir
`agents/collectors/tic.py`, où la première URL supposée s'est révélée fausse
à la vérification réelle). Ce sous-agent accepte donc en entrée un contenu
déjà obtenu — texte (`scope["content"]`) par un futur scraper Playwright ou
fourni manuellement, ou image(s) déjà présente(s) sur disque
(`scope["image_paths"]`, ex. des diagrammes exportés d'une galerie photo) —
exactement comme `synthesis.py` accepte un `report_id` déjà généré plutôt
que de refaire le travail en amont.

Chemin image : décrit via `mistral_client.complete_vision`, avec
`mistral-small-latest` plutôt que `mistral-large-latest` (utilisé pour le
chemin texte) — c'est le modèle dont le support vision est confirmé (Mistral
Small 3.1+), pas une régression de qualité choisie par erreur.

Volontairement non enregistré dans `agents/collectors/__init__.py:COLLECTORS`
(donc pas joignable via `POST /agents/collect`) : le roadmap est explicite,
la veille méthodologique de Jane ne doit tourner qu'en tâche de fond à
faible priorité et ne jamais retarder les modes réactifs/urgence de
l'orchestrateur. Un futur runner de veille continue (ex. un job planifié
séparé) doit appeler `agents.orchestrator.run.run_collection_task(db, engine,
"veille_methodologique", collect_veille_methodologique, scope)` directement,
jamais via l'endpoint HTTP partagé avec les autres sous-agents — voir aussi
le bloc `__main__` de ce module pour un import ponctuel en ligne de commande."""

from __future__ import annotations

import json
import mimetypes
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from agents import jane_knowledge, mistral_client
from agents.orchestrator.types import CollectedItem

# Formats confirmés acceptés par l'API vision de Mistral. Les photos iPhone
# exportées en HEIC (format par défaut de l'appareil photo) doivent être
# converties au préalable (ex. réglage "Le plus compatible" dans Réglages >
# Appareil photo > Formats) -- sinon l'appel échouerait côté API avec une
# erreur peu explicite plutôt que ce message clair.
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

VISION_USER_PROMPT = "Décris ce diagramme d'analyse technique."


def _encode_image_data_uri(path: Path) -> str:
    """Encode une image locale en data URI base64 pour l'API vision de
    Mistral (voir `agents/mistral_client.py:complete_vision`)."""
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
        raise ValueError(
            f"Format d'image non supporté pour « {path.name} » ({mime_type or 'inconnu'}) — "
            f"formats acceptés : {', '.join(sorted(SUPPORTED_IMAGE_MIME_TYPES))}. "
            "Convertir en JPEG/PNG avant import."
        )
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _summarize_content(content: str) -> str:
    system_prompt = mistral_client.load_system_prompt("jane_veille_system.txt")
    user_message = json.dumps({"contenu_source": content}, ensure_ascii=False)
    return mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_LARGE)


def _summarize_images(image_paths: list[str]) -> str:
    image_data_uris = [_encode_image_data_uri(Path(p)) for p in image_paths]
    system_prompt = mistral_client.load_system_prompt("jane_veille_vision_system.txt")
    return mistral_client.complete_vision(system_prompt, VISION_USER_PROMPT, image_data_uris, model=mistral_client.MODEL_SMALL)


def collect_veille_methodologique(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """`scope` doit contenir `source_name`, et exactement un des deux :
    `content` (texte déjà récupéré par ailleurs) ou `image_paths` (chemins
    locaux vers un ou plusieurs diagrammes) — peut aussi contenir
    `source_url`. Résume la source (texte via `mistral-large-latest`, image
    via `mistral-small-latest` — voir docstring du module), puis ajoute le
    résumé à `jane_knowledge` via `agents.jane_knowledge.add_knowledge`, qui
    déduplique par similarité plutôt que de laisser la base grossir de
    quasi-doublons au fil des relectures. Renvoie toujours un seul groupe à
    un seul `CollectedItem` — source unique, donc toujours validée par
    défaut par `agents/orchestrator/validation.py`, même principe que
    `synthesis.py`."""
    if not scope or not scope.get("source_name"):
        raise ValueError("La collecte 'veille_methodologique' requiert 'source_name' dans le périmètre.")

    has_content = bool(scope.get("content"))
    has_images = bool(scope.get("image_paths"))
    if has_content == has_images:  # ni l'un ni l'autre, ou les deux à la fois -- scope ambigu
        raise ValueError(
            "La collecte 'veille_methodologique' requiert soit 'content' (texte), "
            "soit 'image_paths' (diagrammes) dans le périmètre — jamais aucun des deux, jamais les deux."
        )

    summary = _summarize_content(scope["content"]) if has_content else _summarize_images(scope["image_paths"])

    entry = jane_knowledge.add_knowledge(
        db, content=summary, source_name=scope["source_name"], source_url=scope.get("source_url")
    )
    observed_at = entry.created_at.isoformat() if entry is not None else datetime.now(timezone.utc).isoformat()
    status_note = "ajoutée à jane_knowledge" if entry is not None else "quasi-doublon ignoré"

    label = f"Veille méthodologique — {scope['source_name']} ({status_note})"
    item = CollectedItem(
        label=label,
        value=summary,
        unit=None,
        source_name=scope["source_name"],
        source_url=scope.get("source_url"),
        observed_at=observed_at,
    )
    return [(label, [item])]


if __name__ == "__main__":
    import logging
    import sys

    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 3:
        print("Usage : python -m agents.jane_veille <source_name> <image1> [image2 ...]")
        raise SystemExit(1)

    cli_source_name, *cli_image_paths = sys.argv[1:]
    cli_engine = get_engine()
    cli_session_factory = get_session_factory()
    with cli_session_factory() as cli_db:
        result = run_collection_task(
            cli_db,
            cli_engine,
            "veille_methodologique",
            collect_veille_methodologique,
            scope={"source_name": cli_source_name, "image_paths": cli_image_paths},
        )
    print(f"{len(result['validated'])} événement(s) validé(s), {result['quarantined_count']} en quarantaine.")
