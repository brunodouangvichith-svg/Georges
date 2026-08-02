"""Endpoint `/news` — actualités récentes du marché via yfinance (ad hoc,
pas une phase du roadmap), pour la tuile "Breaking News" du mobile. Passe-
plat en direct, sans persistance : contrairement aux fondamentaux/dividendes
(`ingestion/fundamentals.py`), une actualité n'a aucune valeur à être
conservée dans le temps — inutile d'ajouter une table pour ça.

Utilise l'indice CAC 40 (`^FCHI`) plutôt qu'un titre individuel : une
actualité par titre n'aurait de sens que pour le titre sélectionné (déjà
son propre écran de détail), alors que cette tuile vit dans le tableau de
bord général de l'écran Univers, aux côtés des repères macro."""

import logging

import yfinance as yf
from fastapi import APIRouter

from api.schemas import NewsItemOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

NEWS_TICKER = "^FCHI"
MAX_ITEMS = 10


@router.get("", response_model=list[NewsItemOut])
def list_news():
    """Route `def` (pas `async def`, comme `api/routers/prices.py`) :
    l'appel réseau yfinance est bloquant, FastAPI l'exécute alors dans son
    threadpool par défaut plutôt que sur la boucle asyncio. Ne lève jamais
    d'exception côté yfinance/réseau — une liste vide (échec doux, loggé)
    plutôt qu'un 503, cohérent avec le reste des ingestions/collectes de ce
    projet qui traitent une source externe en échec comme un cas normal."""
    try:
        raw_items = yf.Ticker(NEWS_TICKER).news
    except Exception:
        logger.exception("Échec de la récupération des actualités yfinance (%s)", NEWS_TICKER)
        return []

    items = []
    for raw in raw_items[:MAX_ITEMS]:
        content = raw.get("content", {})
        title = content.get("title")
        if not title:
            continue
        items.append(
            NewsItemOut(
                title=title,
                source_name=(content.get("provider") or {}).get("displayName", "Yahoo Finance"),
                published_at=content.get("pubDate"),
                url=(content.get("canonicalUrl") or {}).get("url"),
            )
        )
    return items
