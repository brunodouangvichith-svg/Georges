"""Sous-agent de collecte "synthèse de document" (Phase 7, MVP, tâche 1) —
résume un `Report` déjà généré (Phase 4, `agents/reports.py`) en quelques
indicateurs exploitables via un appel Mistral dédié. Remplace le sous-agent
"fondamentaux d'entreprise" (SEC EDGAR) prévu par la roadmap : EDGAR ne
couvre que ~5-6 des 102 titres de l'univers CAC 40/Mid 60 (vérifié contre
`company_tickers.json` de la SEC), une lacune de couverture jugée trop
importante. Réutilise des données déjà réelles et déjà
anti-hallucination-vérifiées (`Report.content`) plutôt que d'introduire une
nouvelle dépendance externe."""

from __future__ import annotations

import json

from agents import mistral_client
from agents.orchestrator.types import CollectedItem
from ingestion.models import Report


def collect_synthese_document(db, engine, scope: dict | None) -> list[tuple[str, list[CollectedItem]]]:
    """`scope["report_id"]` est obligatoire. Lève `ValueError` si absent ou
    si le rapport n'existe pas (traduit en 404 par `api/routers/agents.py`).
    Renvoie toujours un seul groupe à un seul `CollectedItem` — une synthèse
    interne n'a qu'une seule source (le rapport lui-même), donc toujours
    validée par défaut (`agents/orchestrator/validation.py`), sauf échec
    Mistral qui remonte tel quel (`MistralUnavailableError`, déjà géré par
    `api/main.py`)."""
    if not scope or "report_id" not in scope:
        raise ValueError("La collecte 'synthese_document' requiert un report_id dans le périmètre.")

    report = db.get(Report, scope["report_id"])
    if report is None:
        raise ValueError(f"Rapport introuvable : {scope['report_id']}")

    system_prompt = mistral_client.load_system_prompt("synthesis_system.txt")
    user_message = json.dumps({"contenu_rapport": report.content}, ensure_ascii=False)
    summary = mistral_client.complete(system_prompt, user_message, model=mistral_client.MODEL_SMALL)

    label = f"Synthèse du rapport #{report.id}"
    item = CollectedItem(
        label=label,
        value=summary,
        unit=None,
        source_name="Rapport interne",
        source_url=None,
        observed_at=report.created_at.isoformat(),
    )
    return [(label, [item])]
