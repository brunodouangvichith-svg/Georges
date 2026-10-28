"""Endpoints `/cron` — déclenchement des jobs de collecte/entraînement
jusqu'ici réservés à `.github/workflows/*.yml` (ad hoc, pas une phase du
roadmap, ajouté octobre 2026). Mis en place quand la limite de dépenses
GitHub Actions du dépôt a bloqué TOUS les workflows planifiés pendant
plusieurs semaines sans que l'utilisateur ne la relève (voir CLAUDE.md) —
un Worker Cloudflare (Cron Triggers, gratuit) appelle désormais ces routes
sur le même calendrier que les workflows GitHub d'origine, qui restent en
place comme déclenchement manuel de secours (`workflow_dispatch`) plutôt
que supprimés.

Protégées par `require_cron_secret` (secret partagé, en-tête
`X-Cron-Secret`), PAS `require_user` (voir le docstring de cette fonction
dans `api/auth.py`) — ce routeur n'est donc PAS enregistré avec
`dependencies=[Depends(require_user)]` dans `api/main.py`, contrairement à
tous les autres.

Chaque route lance le job en tâche de fond (`BackgroundTasks`) et renvoie
immédiatement : le Worker Cloudflare a lui-même un budget d'exécution
limité (CPU ms par requête) et n'a pas vocation à attendre la fin d'un job
qui peut prendre plusieurs minutes (fondamentaux, détection, entraînement
du modèle) — le détail de l'exécution (succès, échecs par titre/entreprise/
pays) reste dans les logs Render, comme c'était déjà le cas dans les logs
du runner GitHub Actions d'origine. Aucun état de suivi exposé (pas de
`GET /cron/.../status`) : personne ne consulte ces jobs après coup, à la
différence de `POST /prices/refresh` (polling par l'UI web/mobile)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from api.auth import require_cron_secret
from api.schemas import CronTriggerResponse

router = APIRouter(prefix="/cron", tags=["cron"], dependencies=[Depends(require_cron_secret)])

logger = logging.getLogger(__name__)


def _run_bonds() -> None:
    from engine.bond_alerts import evaluate_all_thresholds
    from ingestion import bond_yields
    from ingestion.db import get_session_factory
    from ingestion.seed_bond_alert_thresholds import seed_bond_alert_thresholds

    seed_bond_alert_thresholds()
    summary = bond_yields.run()
    with get_session_factory()() as db:
        created = evaluate_all_thresholds(db)
    logger.info("cron bonds : %s, %d alerte(s) créée(s).", summary, len(created))


def _run_energy_prices() -> None:
    from ingestion import energy_prices

    summary = energy_prices.run()
    logger.info("cron energy-prices : %s", summary)


def _run_fundamentals() -> None:
    from ingestion import fundamentals

    summary = fundamentals.run()
    ok = sum(1 for v in summary.values() if v["fundamentals"])
    logger.info("cron fundamentals : %d/%d titres mis à jour.", ok, len(summary))


def _run_george_veille() -> None:
    from agents import george_veille

    logger.info("cron george-veille : %s", george_veille.run())


def _run_geopolitical_veille() -> None:
    from agents import geopolitical_veille

    logger.info("cron geopolitical-veille : %s", geopolitical_veille.run())


def _run_jane_veille_web() -> None:
    from agents import jane_veille

    logger.info("cron jane-veille-web : %s", jane_veille.run_web())


def _run_price_history_and_detection() -> None:
    from engine import propose_decisions, run_detection
    from ingestion import price_history

    history_summary = price_history.run()
    pattern_count = run_detection.run()
    proposed = propose_decisions.run()
    logger.info(
        "cron price-history-and-detection : %s, %d figure(s) détectée(s), %d décision(s) proposée(s).",
        history_summary,
        pattern_count,
        len(proposed),
    )


def _run_confidence_model_training() -> None:
    from engine import build_training_set, train_confidence_model

    build_training_set.run()
    report = train_confidence_model.train_candidate()
    # Pas d'artifact téléversé ici, contrairement au workflow GitHub d'origine
    # (`actions/upload-artifact`) : le disque de ce service Render n'est pas
    # garanti persistant au-delà d'un déploiement. Le candidat est bien écrit
    # localement (`engine/models/candidates/`, voir train_confidence_model.py)
    # mais le rapport est aussi loggé en clair pour rester consultable même si
    # le fichier disparaît avant une promotion manuelle
    # (`python -m engine.promote_candidate_model`, toujours humaine, jamais
    # automatique).
    logger.info("cron confidence-model-training :\n%s", train_confidence_model.format_report(report))


@router.post("/bonds", response_model=CronTriggerResponse)
def trigger_bonds(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_bonds)
    return CronTriggerResponse(status="started", job="bonds")


@router.post("/energy-prices", response_model=CronTriggerResponse)
def trigger_energy_prices(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_energy_prices)
    return CronTriggerResponse(status="started", job="energy-prices")


@router.post("/fundamentals", response_model=CronTriggerResponse)
def trigger_fundamentals(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_fundamentals)
    return CronTriggerResponse(status="started", job="fundamentals")


@router.post("/george-veille", response_model=CronTriggerResponse)
def trigger_george_veille(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_george_veille)
    return CronTriggerResponse(status="started", job="george-veille")


@router.post("/geopolitical-veille", response_model=CronTriggerResponse)
def trigger_geopolitical_veille(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_geopolitical_veille)
    return CronTriggerResponse(status="started", job="geopolitical-veille")


@router.post("/jane-veille-web", response_model=CronTriggerResponse)
def trigger_jane_veille_web(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_jane_veille_web)
    return CronTriggerResponse(status="started", job="jane-veille-web")


@router.post("/price-history-and-detection", response_model=CronTriggerResponse)
def trigger_price_history_and_detection(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_price_history_and_detection)
    return CronTriggerResponse(status="started", job="price-history-and-detection")


@router.post("/confidence-model-training", response_model=CronTriggerResponse)
def trigger_confidence_model_training(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_confidence_model_training)
    return CronTriggerResponse(status="started", job="confidence-model-training")
