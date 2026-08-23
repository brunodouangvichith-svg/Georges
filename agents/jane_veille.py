"""Sous-agent de veille méthodologique de Jane (Phase 7) — résume un contenu
déjà récupéré (article, page de référence, note) et l'ajoute à
`jane_knowledge` (`agents/jane_knowledge.py`), pour un enrichissement continu
du savoir sur lequel s'appuie `agents.jane.second_opinion` (voir
`agents/jane.py`).

Décision de scope (MVP, même discipline que `agents/collectors/synthesis.py`
remplaçant EDGAR) : ce module ne scrape pas lui-même Investopedia/BabyPips/
TradingView/ProRealTime/NanoTrader — le roadmap (Phase 7) prévoit Playwright/
Scrapy pour ça, une dépendance non encore ajoutée au projet, et du code de
scraping non vérifié en direct contre ces sites précis serait plus
susceptible de casser silencieusement que d'apporter une vraie valeur (voir
`agents/collectors/tic.py`, où la première URL supposée s'est révélée fausse
à la vérification réelle). Ce sous-agent accepte donc en entrée un contenu
déjà obtenu (`scope["content"]`) — par un futur scraper Playwright, ou
fourni manuellement en attendant — exactement comme `synthesis.py` accepte
un `report_id` déjà généré plutôt que de refaire le travail en amont.

Volontairement non enregistré dans `agents/collectors/__init__.py:COLLECTORS`
(donc pas joignable via `POST /agents/collect`) : le roadmap est explicite,
la veille méthodologique de Jane ne doit tourner qu'en tâche de fond à
faible priorité et ne jamais retarder les modes réactifs/urgence de
l'orchestrateur. Un futur runner de veille continue (ex. un job planifié
séparé) doit appeler `agents.orchestrator.run.run_collection_task(db, engine,
"veille_methodologique", collect_veille_methodologique, scope)` directement,
jamais via l'endpoint HTTP partagé avec les autres sous-agents."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agents import jane_knowledge, mistral_client
from agents.orchestrator.types import CollectedItem

REQUIRED_SCOPE_KEYS = ("source_name", "content")


def collect_veille_methodologique(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """`scope` doit contenir `source_name` et `content` (texte déjà récupéré
    par ailleurs) et peut contenir `source_url`. Résume `content` via Mistral
    (`mistral-large-latest` — la qualité d'extraction prime ici sur la
    latence, comme prévu par le roadmap pour Jane), puis ajoute le résumé à
    `jane_knowledge` via `agents.jane_knowledge.add_knowledge`, qui
    déduplique par similarité plutôt que de laisser la base grossir de
    quasi-doublons au fil des relectures. Renvoie toujours un seul groupe à
    un seul `CollectedItem` — source unique, donc toujours validée par
    défaut par `agents/orchestrator/validation.py`, même principe que
    `synthesis.py`."""
    if not scope or not all(scope.get(k) for k in REQUIRED_SCOPE_KEYS):
        raise ValueError("La collecte 'veille_methodologique' requiert 'source_name' et 'content' dans le périmètre.")

    system_prompt = mistral_client.load_system_prompt("jane_veille_system.txt")
    user_message = json.dumps({"contenu_source": scope["content"]}, ensure_ascii=False)
    summary = mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_LARGE)

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
