"""Endpoints `/strategic-reports` — Rapport stratégique hebdomadaire (onglet
« Rapport », web et mobile). Génération à la demande, asynchrone, même schéma
que `api/routers/prices.py` : `POST /generate` lance le job en tâche de fond
et répond tout de suite, les clients font un `GET /generate` en polling
jusqu'à `done`/`failed`. Un seul job à la fois (`_lock`) : un second `POST`
pendant une génération renvoie l'état en cours au lieu d'en lancer une autre
(chaque génération passe des ordres simulés : deux en parallèle doubleraient
les achats du portefeuille virtuel).

La génération ouvre ses propres sessions sur un moteur dédié sans pool
(`_job_engine`, construit depuis `deps.engine.url` lu à l'appel) et ne garde aucune connexion ouverte pendant
les appels Tavily/yfinance/Mistral — voir `agents/strategic_report.py`."""

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from agents import strategic_report
from api import deps
from api.deps import get_db
from api.schemas import StrategicReportJobStatus, StrategicReportOut, StrategicReportSummaryOut
from ingestion.db import CONNECT_TIMEOUT_SECONDS
from ingestion.models import StrategicReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategic-reports", tags=["strategic-reports"])

_lock = threading.Lock()
_state: dict = {"status": "idle"}


def _job_engine():
    """Moteur dédié au job, sans pool (`NullPool`) : une connexion ouverte à
    la demande puis fermée. Le job ne passe donc jamais dans la file d'attente
    du pool de l'API (2 + 2 connexions) — en production, l'écran Univers
    pouvait l'occuper entièrement pendant plus de 30 s et la génération
    échouait sur « QueuePool limit of size 2 overflow 2 reached ». Le job
    n'ouvre qu'une connexion à la fois (jamais pendant les appels réseau),
    donc au plus une connexion de plus côté Supabase. Construit depuis
    `deps.engine.url`, lu à l'appel (remplaçable en test)."""
    return create_engine(
        deps.engine.url,
        poolclass=NullPool,
        future=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


def _run_generation_job() -> None:
    global _state
    job_engine = None
    try:
        job_engine = _job_engine()
        session_factory = sessionmaker(bind=job_engine, autoflush=False, future=True)
        report_id = strategic_report.generate_report(session_factory)
        with _lock:
            _state = {
                "status": "done",
                "started_at": _state.get("started_at"),
                "finished_at": datetime.now(timezone.utc),
                "report_id": report_id,
            }
    except Exception as exc:  # noqa: BLE001 - job de fond : l'erreur doit atterrir dans le statut
        logger.exception("La génération du rapport stratégique a échoué")
        with _lock:
            _state = {
                "status": "failed",
                "started_at": _state.get("started_at"),
                "finished_at": datetime.now(timezone.utc),
                "error": str(exc),
            }
    finally:
        if job_engine is not None:
            job_engine.dispose()


@router.post("/generate", response_model=StrategicReportJobStatus)
def generate(background_tasks: BackgroundTasks):
    global _state
    with _lock:
        if _state.get("status") == "running":
            return StrategicReportJobStatus(**_state)
        _state = {"status": "running", "started_at": datetime.now(timezone.utc)}
        snapshot = dict(_state)
    background_tasks.add_task(_run_generation_job)
    return StrategicReportJobStatus(**snapshot)


@router.get("/generate", response_model=StrategicReportJobStatus)
def generation_status():
    with _lock:
        return StrategicReportJobStatus(**_state)


@router.get("", response_model=list[StrategicReportSummaryOut])
def list_reports(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    stmt = select(StrategicReport).order_by(StrategicReport.created_at.desc(), StrategicReport.id.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/latest", response_model=StrategicReportOut | None)
def latest_report(db: Session = Depends(get_db)):
    """`null` (200) tant qu'aucun rapport n'a été généré — un état normal, pas
    une erreur."""
    stmt = select(StrategicReport).order_by(StrategicReport.created_at.desc(), StrategicReport.id.desc()).limit(1)
    return db.execute(stmt).scalars().first()


@router.get("/{report_id}", response_model=StrategicReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(StrategicReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable.")
    return report
