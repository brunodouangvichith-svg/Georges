"""Endpoints `/strategic-reports` — Rapport stratégique hebdomadaire (onglet
« Rapport », web et mobile). Génération à la demande, asynchrone, même schéma
que `api/routers/prices.py` : `POST /generate` lance le job en tâche de fond
et répond tout de suite, les clients font un `GET /generate` en polling
jusqu'à `done`/`failed`. Un seul job à la fois (`_lock`) : un second `POST`
pendant une génération renvoie l'état en cours au lieu d'en lancer une autre
(chaque génération passe des ordres simulés : deux en parallèle doubleraient
les achats du portefeuille virtuel).

La génération ouvre ses propres sessions (`deps.SessionLocal`, lu à l'appel
pour rester remplaçable en test) et ne garde aucune connexion ouverte pendant
les appels Tavily/yfinance/Mistral — voir `agents/strategic_report.py`."""

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents import strategic_report
from api import deps
from api.deps import get_db
from api.schemas import StrategicReportJobStatus, StrategicReportOut, StrategicReportSummaryOut
from ingestion.models import StrategicReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategic-reports", tags=["strategic-reports"])

_lock = threading.Lock()
_state: dict = {"status": "idle"}


def _run_generation_job() -> None:
    global _state
    try:
        report_id = strategic_report.generate_report(deps.SessionLocal)
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
