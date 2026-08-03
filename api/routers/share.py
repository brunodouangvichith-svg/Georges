"""`POST /share/email` — partage par email d'une popup de réponse de George
(ad hoc, pas une phase du roadmap), demandé directement par l'utilisateur.

Le texte brut est reformulé par Mistral avant envoi (`agents.email_formatter`,
retombe sur le texte brut si Mistral est indisponible), et si `symbol` est
fourni, le graphique 10 ans du titre (`price_history_long`) est joint en
pièce jointe PNG (`engine.chart_image`) — silencieusement omis, jamais une
erreur, si le titre est inconnu ou n'a pas d'historique de prix : le
graphique est un enrichissement, pas une condition de l'envoi. La figure la
plus récemment détectée pour ce titre (même tri que
`api/routers/securities.py` : `detected_at` puis `confidence` décroissants)
est surlignée sur ce graphique si elle existe — sans figure, un historique
de prix nu, jamais une figure inventée."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import engine.chart_image as chart_image
import engine.run_detection as run_detection
import notifications.email_client as email_client
from agents import email_formatter
from api import deps
from api.deps import get_db
from api.schemas import ShareEmailRequest, ShareEmailResponse
from ingestion.models import PatternDetected

router = APIRouter(prefix="/share", tags=["share"])


def _latest_pattern(db: Session, symbol: str) -> PatternDetected | None:
    stmt = (
        select(PatternDetected)
        .where(PatternDetected.symbol == symbol)
        .order_by(PatternDetected.detected_at.desc(), PatternDetected.confidence.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


@router.post("/email", response_model=ShareEmailResponse)
def share_by_email(request: ShareEmailRequest, db: Session = Depends(get_db)):
    """Route en `def`, pas `async def` : FastAPI l'exécute dans son
    threadpool par défaut, cohérent avec les autres actions potentiellement
    longues de ce projet (`api/routers/prices.py`) — reformulation LLM,
    rendu d'image et appel HTTP à Resend sont tous des I/O bloquants.

    Modules importés entiers (`chart_image`, `run_detection`, `email_client`,
    `email_formatter`), jamais leurs fonctions directement — même précédent
    que `agents/mistral_client.py`/`api/routers/baskets.py:deps.engine` :
    permet à `monkeypatch.setattr(module, "func", fake)` de s'appliquer
    réellement, quel que soit l'ordre d'import."""
    body = email_formatter.format_email_body(request.text)

    attachment_bytes = None
    chart_attached = False
    if request.symbol:
        df = run_detection.load_prices(deps.engine, request.symbol)
        if not df.empty:
            pattern = _latest_pattern(db, request.symbol)
            attachment_bytes = chart_image.render_candlestick_png(
                df, f"{request.symbol} — 10 ans", context=pattern.context if pattern else None
            )
            chart_attached = True

    email_client.send_email(
        to_email=request.to_email,
        subject=request.subject,
        text=body,
        attachment_bytes=attachment_bytes,
        attachment_filename=f"{request.symbol}.png" if request.symbol else None,
    )
    return ShareEmailResponse(sent=True, chart_attached=chart_attached)
