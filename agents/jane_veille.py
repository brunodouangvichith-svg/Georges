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
mode `--batch` pour plusieurs entrées déjà résumées d'un coup).

`collect_veille_web` (ajouté plus tard, demandé directement par
l'utilisateur : "que Jane mette à jour ses connaissances en continue... en
faisant des recherches sur internet") change la donne ci-dessus : `agents.
web_search` (Tavily, voir sa docstring) fournit du contenu web réel et
propre sans avoir besoin de Playwright/Scrapy — ce n'est plus du scraping
maison spécifique à un site, juste un appel API comme n'importe quel autre
`ingestion.*`/`agents.collectors.*` de ce projet. Contrairement à
`collect_veille_methodologique` (contenu déjà fourni en `scope`), cette
fonction fait sa propre recherche à partir d'un sujet. Reste soumis à la
même contrainte de fond que ci-dessus (non enregistré dans `COLLECTORS`,
tourne via un job planifié séparé — voir `.github/workflows/
weekly_jane_veille_web.yml`), et à la même dédup par similarité de
`jane_knowledge.add_knowledge`."""

from __future__ import annotations

import json
import mimetypes
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

from agents import jane_knowledge, mistral_client, web_search
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

# Amorcé depuis `George_AnalyseTechnique_Kabbaj_Synthese.md`, qui catalogue
# déjà ces concepts comme identifiés-mais-non-implémentés dans George — une
# liste de sujets à faire évoluer au besoin, pas figée.
VEILLE_WEB_TOPICS = [
    "doji hammer engulfing candlestick patterns",
    "Elliott Wave theory trading",
    "Fibonacci retracement technical analysis",
    "RSI divergence trading strategy",
    "RSI overbought oversold price objective",
    "pair trading strategy statistical arbitrage",
    "Livermore pyramiding position sizing",
    "MACD histogram trading strategy",
    "Bollinger Bands squeeze breakout",
    "volume profile trading analysis",
]

# Nombre de résultats web indépendants récupérés par sujet — plusieurs, pas
# un seul, pour que `collect_veille_web` puisse recouper l'information
# (garde-fou 2 de `jane_veille_web_system.txt`) plutôt que de faire confiance
# à une seule source.
VEILLE_WEB_RESULTS_PER_TOPIC = 3


def _pick_weekly_topic(topics: list[str] = VEILLE_WEB_TOPICS) -> str:
    """Rotation déterministe sans état à mémoriser nulle part (pas de
    marqueur, pas de nouvelle colonne/table) : le numéro de semaine ISO
    choisit le sujet, donc chaque sujet revient environ tous les
    `len(topics)` semaines. Suffisant pour une veille de fond à faible
    priorité — inutile de suivre "le dernier sujet traité" pour ça."""
    week_number = datetime.now(timezone.utc).isocalendar().week
    return topics[week_number % len(topics)]


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


def collect_veille_web(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """Recherche web réelle (`agents.web_search`, Tavily) sur un sujet
    d'analyse technique et l'ajoute à `jane_knowledge` — voir la docstring du
    module pour la différence avec `collect_veille_methodologique` (contenu
    déjà fourni). `scope["topic"]` est optionnel : à défaut, un sujet est
    choisi par rotation hebdomadaire déterministe (`_pick_weekly_topic`)
    parmi `VEILLE_WEB_TOPICS`.

    Fiabilité ("accurate", demandé explicitement par l'utilisateur) :
    `VEILLE_WEB_RESULTS_PER_TOPIC` résultats indépendants sont récupérés pour
    le même sujet et synthétisés ENSEMBLE en un seul appel Mistral
    (`agents/prompts/jane_veille_web_system.txt`), jamais un par un — même
    logique de recoupement multi-sources que
    `agents/orchestrator/validation.py`, adaptée à du texte plutôt qu'à des
    valeurs numériques comparables directement : le prompt système instruit
    Jane à prioriser ce qui est confirmé par au moins deux sources et à
    signaler les désaccords plutôt que d'inventer un consensus. Aucun
    résultat Tavily (clé absente, service en échec) renvoie une liste vide
    plutôt qu'une erreur — cette fonction est censée tourner sans
    supervision via un job planifié (voir le docstring du module), une
    absence de résultat pour un sujet donné une semaine donnée n'est pas un
    échec à remonter bruyamment."""
    topic = (scope or {}).get("topic") or _pick_weekly_topic()
    results = web_search.search(f"{topic} analyse technique trading", max_results=VEILLE_WEB_RESULTS_PER_TOPIC)
    if not results:
        return []

    sources_payload = json.dumps(
        [{"titre": r["titre"], "extrait": r["extrait"], "url": r["url"]} for r in results],
        ensure_ascii=False,
    )
    system_prompt = mistral_client.load_system_prompt("jane_veille_web_system.txt")
    summary = mistral_client.complete(system_prompt, sources_payload, model=mistral_client.MODEL_LARGE)

    source_name = f"Recherche web ({len(results)} sources) — {topic}"
    entry = jane_knowledge.add_knowledge(db, content=summary, source_name=source_name, source_url=results[0]["url"])
    observed_at = entry.created_at.isoformat() if entry is not None else datetime.now(timezone.utc).isoformat()
    status_note = ADDED_STATUS_NOTE if entry is not None else DUPLICATE_STATUS_NOTE

    label = f"Veille web — {topic} ({status_note})"
    item = CollectedItem(
        label=label,
        value=summary,
        unit=None,
        source_name=source_name,
        source_url=results[0]["url"],
        observed_at=observed_at,
    )
    return [(label, [item])]


def run_web(topic: str | None = None) -> dict:
    """Point d'entrée réutilisable pour `collect_veille_web`, extrait de la
    branche `--web` du `__main__` d'origine (octobre 2026) — appelé par la
    CLI et par `POST /cron/jane-veille-web` (`api/routers/cron.py`), même
    raison que `agents/george_veille.py:run`."""
    from agents.orchestrator.run import run_collection_task
    from ingestion.db import get_engine, get_session_factory

    scope = {"topic": topic} if topic else None
    engine = get_engine()
    session_factory = get_session_factory()
    with session_factory() as db:
        result = run_collection_task(db, engine, "veille_web", collect_veille_web, scope)
    return {"added": len(result["validated"])}


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
            "  python -m agents.jane_veille --batch <fichier.json>\n"
            "  python -m agents.jane_veille --web [sujet]"
        )
        raise SystemExit(1)

    if sys.argv[1] == "--batch":
        if len(sys.argv) != 3:
            print("Usage : python -m agents.jane_veille --batch <fichier.json>")
            raise SystemExit(1)
        _run_batch(sys.argv[2])
        raise SystemExit(0)

    if sys.argv[1] == "--web":
        # Sujet explicite optionnel (ex. tester un sujet précis en dehors de
        # la rotation hebdomadaire) -- sans argument, `collect_veille_web`
        # choisit elle-même via `_pick_weekly_topic`, comportement normal du
        # job planifié (voir `.github/workflows/weekly_jane_veille_web.yml`).
        web_topic = sys.argv[2] if len(sys.argv) > 2 else None
        web_summary = run_web(web_topic)
        added = web_summary["added"]
        print(f"{added} entrée(s) ajoutée(s) à jane_knowledge." if added else "Aucune entrée ajoutée (pas de résultat web, ou quasi-doublon).")
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
