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

`scope["already_summarized"]` (texte uniquement) : saute l'appel Mistral de
résumé et ajoute `content` tel quel à `jane_knowledge` — pour un texte déjà
rédigé comme une entrée de connaissance finale (ex. une description
qu'un humain, ou un autre agent multimodal, a déjà écrite en lisant l'image
directement plutôt que via l'API vision), pour ne pas le faire reformuler/
dériver par un second appel LLM inutile.

Volontairement non enregistré dans `agents/collectors/__init__.py:COLLECTORS`
(donc pas joignable via `POST /agents/collect`) : le roadmap est explicite,
la veille méthodologique de Jane ne doit tourner qu'en tâche de fond à
faible priorité et ne jamais retarder les modes réactifs/urgence de
l'orchestrateur. Un futur runner de veille continue (ex. un job planifié
séparé) doit appeler `agents.orchestrator.run.run_collection_task(db, engine,
"veille_methodologique", collect_veille_methodologique, scope)` directement,
jamais via l'endpoint HTTP partagé avec les autres sous-agents — voir aussi
le bloc `__main__` de ce module (import en ligne de commande, y compris un
mode `--batch` pour plusieurs entrées déjà résumées d'un coup)."""

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

# Marqueur partagé entre `collect_veille_methodologique` (qui l'écrit dans le
# label/description de l'AgentEvent) et `_run_batch` (qui le relit pour
# compter les vrais doublons -- `quarantined_count` de l'orchestrateur ne
# convient pas ici : une source unique est toujours "validated" par
# `agents/orchestrator/validation.py`, quel que soit le verdict réel de
# `jane_knowledge.add_knowledge`).
DUPLICATE_STATUS_NOTE = "quasi-doublon ignoré"
ADDED_STATUS_NOTE = "ajoutée à jane_knowledge"


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
    `source_url` et, pour `content` uniquement, `already_summarized` (voir
    docstring du module). Résume la source (texte via `mistral-large-latest`,
    image via `mistral-small-latest` — voir docstring du module), sauf
    `already_summarized=True` qui saute cette étape, puis ajoute le résultat
    à `jane_knowledge` via `agents.jane_knowledge.add_knowledge`, qui
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

    already_summarized = scope.get("already_summarized", False)
    # Un fichier --batch édité à la main peut écrire par erreur la chaîne
    # "false" (avec guillemets) plutôt que le booléen JSON false -- une
    # chaîne non vide est truthy en Python, ce qui activerait silencieusement
    # ce chemin. Exiger un vrai booléen transforme cette faute de frappe en
    # erreur explicite plutôt qu'en contenu non résumé écrit par erreur.
    if not isinstance(already_summarized, bool):
        raise ValueError(f"'already_summarized' doit être un booléen JSON (true/false), pas {already_summarized!r}.")
    if already_summarized and not has_content:
        raise ValueError("'already_summarized' ne s'applique qu'au chemin texte ('content'), jamais à 'image_paths'.")

    if has_images:
        summary = _summarize_images(scope["image_paths"])
    elif already_summarized:
        summary = scope["content"]
    else:
        summary = _summarize_content(scope["content"])

    entry = jane_knowledge.add_knowledge(
        db, content=summary, source_name=scope["source_name"], source_url=scope.get("source_url")
    )
    observed_at = entry.created_at.isoformat() if entry is not None else datetime.now(timezone.utc).isoformat()
    status_note = ADDED_STATUS_NOTE if entry is not None else DUPLICATE_STATUS_NOTE

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


def _run_batch(batch_path: str) -> None:
    """`--batch <fichier.json>` : importe plusieurs entrées d'un coup, sous
    la forme d'une liste JSON de `scope` (mêmes clés que
    `collect_veille_methodologique` — `source_name` + `content`/
    `image_paths`). Pensé pour des descriptions déjà rédigées
    (`already_summarized: true`) — ex. par un agent multimodal ayant lu les
    images directement en conversation plutôt que via l'API vision — sans
    empêcher d'y mélanger des entrées `image_paths` classiques.

    Une entrée qui échoue (scope malformé, appel Mistral/DB en erreur) est
    loguée et sautée plutôt que d'interrompre tout le lot — sur un fichier de
    dizaines d'entrées, une seule faute de frappe ne doit pas faire perdre le
    traitement de toutes les autres. `db.rollback()` après un échec est
    indispensable : sans lui, une session SQLAlchemy ayant échoué en cours de
    transaction reste invalide pour toutes les entrées suivantes
    (`PendingRollbackError`), ce qui ferait échouer en cascade tout le reste
    du lot au lieu de la seule entrée fautive.

    Limite connue (héritée de `agents/orchestrator/run.py`, pas propre au
    mode batch) : `jane_knowledge.add_knowledge` commit son insertion
    indépendamment du commit de l'`AgentEvent` fait ensuite par
    `run_collection_task`. Si le second échoue après le premier (rare,
    coupure DB entre les deux), l'entrée compte comme un échec dans le
    résumé alors que son contenu est déjà écrit dans `jane_knowledge` --
    un relancement du même fichier la retrouvera alors comme quasi-doublon
    plutôt que comme manquante. Accepté tel quel : corriger nécessiterait de
    changer le contrat générique de `run_collection_task`, partagé par tous
    les sous-agents, pour un cas limite rare."""
    import logging

    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    # Ouverture + parsing dans le même bloc : un chemin introuvable
    # (typo courante en ligne de commande) doit donner le même message
    # clair qu'un JSON malformé, jamais une trace Python brute.
    try:
        with open(batch_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except OSError as err:
        raise SystemExit(f"Fichier batch introuvable ou illisible ({batch_path}) : {err}") from err
    except json.JSONDecodeError as err:
        # En dehors du try/except par entrée plus bas : un fichier entier
        # invalide (JSON malformé) n'a pas d'entrées à sauter une par
        # une, mieux vaut un message clair qu'une trace brute.
        raise SystemExit(f"Fichier batch invalide ({batch_path}) : JSON malformé -- {err}") from err
    if not isinstance(entries, list):
        raise SystemExit(f"Fichier batch invalide ({batch_path}) : attendu une liste JSON d'entrées, reçu {type(entries).__name__}.")

    engine = get_engine()
    session_factory = get_session_factory()
    total_added, total_duplicates, total_failed = 0, 0, 0
    with session_factory() as db:
        for entry_scope in entries:
            # Valeur de repli fixée AVANT le `try` : une entrée malformée au
            # point de ne même pas être un dict (ex. un fichier batch mal
            # édité à la main) ne doit pas planter avant d'avoir pu être
            # comptée comme un échec.
            source_name = "(entrée invalide)"
            try:
                if isinstance(entry_scope, dict):
                    source_name = entry_scope.get("source_name", "(source_name manquant)")
                result = run_collection_task(db, engine, "veille_methodologique", collect_veille_methodologique, entry_scope)
            except Exception:  # noqa: BLE001 -- une entrée en erreur ne doit jamais interrompre les suivantes
                logging.exception("Échec de l'import pour « %s » -- entrée sautée.", source_name)
                db.rollback()
                total_failed += 1
                continue

            # `result["quarantined_count"]` ne convient pas pour compter les doublons : une
            # source unique est toujours "validated" par agents/orchestrator/validation.py,
            # quel que soit le verdict réel de jane_knowledge.add_knowledge (voir DUPLICATE_STATUS_NOTE).
            # Limitation acceptée : ce test repère le marqueur dans le texte libre de
            # `AgentEvent.description` (couplage faible avec `_format_single`) -- suffisant
            # pour un résumé de CLI ponctuel, pas une valeur consommée par un autre système.
            is_duplicate = bool(result["validated"]) and f"({DUPLICATE_STATUS_NOTE})" in result["validated"][0].description
            if is_duplicate:
                total_duplicates += 1
            else:
                total_added += len(result["validated"])
            logging.info("%s : %s", source_name, DUPLICATE_STATUS_NOTE if is_duplicate else ADDED_STATUS_NOTE)
    print(
        f"{total_added} entrée(s) ajoutée(s), {total_duplicates} quasi-doublon(s) ignoré(s), "
        f"{total_failed} échec(s) sur {len(entries)}."
    )


if __name__ == "__main__":
    import logging
    import sys

    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print(
            "Usage :\n"
            "  python -m agents.jane_veille <source_name> <image1> [image2 ...]\n"
            "  python -m agents.jane_veille --batch <fichier.json>"
        )
        raise SystemExit(1)

    if sys.argv[1] == "--batch":
        if len(sys.argv) != 3:
            print("Usage : python -m agents.jane_veille --batch <fichier.json>")
            raise SystemExit(1)
        _run_batch(sys.argv[2])
        raise SystemExit(0)

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
