from agents.collectors.eurostat import collect_donnees_eurostat
from agents.collectors.macro import collect_donnees_macro
from agents.collectors.synthesis import collect_synthese_document
from agents.collectors.tic import collect_donnees_tic

# Registre des sous-agents de collecte (Phase 7, MVP) — chacun un module
# indépendant avec un périmètre d'écriture limité (voir
# agents/orchestrator/run.py, seul point d'écriture réel en base). Même
# pattern que engine/patterns/__init__.py:DETECTORS.
#
# `donnees_finnhub` a été décommissionné (agents/collectors/finnhub.py
# supprimé) : le palier gratuit de Finnhub ne couvre pas Euronext Paris
# (403 confirmé en direct sur tous les tickers `.PA` testés, voir
# CLAUDE.md), et il n'a jamais été câblé dans une UI web/mobile — un
# collecteur inutilisable pour cet univers, gardé mort n'apportait rien.
COLLECTORS = {
    "donnees_macro": collect_donnees_macro,
    "synthese_document": collect_synthese_document,
    "donnees_eurostat": collect_donnees_eurostat,
    "donnees_tic": collect_donnees_tic,
}

__all__ = [
    "COLLECTORS",
    "collect_donnees_macro",
    "collect_synthese_document",
    "collect_donnees_eurostat",
    "collect_donnees_tic",
]
