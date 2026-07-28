from agents.collectors.macro import collect_donnees_macro
from agents.collectors.synthesis import collect_synthese_document

# Registre des sous-agents de collecte (Phase 7, MVP) — chacun un module
# indépendant avec un périmètre d'écriture limité (voir
# agents/orchestrator/run.py, seul point d'écriture réel en base). Même
# pattern que engine/patterns/__init__.py:DETECTORS.
COLLECTORS = {
    "donnees_macro": collect_donnees_macro,
    "synthese_document": collect_synthese_document,
}

__all__ = ["COLLECTORS", "collect_donnees_macro", "collect_synthese_document"]
