"""Schémas Pydantic de réponse de l'API (Phase 3).

Toutes les listes sont enveloppées dans le même schéma générique de
pagination (`Page[T]`) : `{"items": [...], "total": N, "limit": L, "offset": O}`.
"""

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class SecurityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    country: str
    currency: str
    sector: str
    theme: str | None = None


class PriceBarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class PatternOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    pattern_type: str
    detected_at: datetime
    confidence: float
    context: dict


class FundamentalsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    observed_at: date
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    currency: str | None = None
    exchange: str | None = None
    long_name: str | None = None
    website: str | None = None
    long_business_summary: str | None = None
    full_time_employees: int | None = None
    market_cap: int | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class DividendOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    ex_date: date
    amount: float


class EnergyPriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commodity_code: str
    price: float
    unit: str
    currency: str
    change_24h_pct: float | None = None
    price_observed_at: datetime | None = None
    snapshot_date: date


class NewsItemOut(BaseModel):
    """Voir `api/routers/news.py` — pas de `model_config(from_attributes=True)`
    ici : construit directement depuis un dict yfinance, pas un objet ORM."""

    title: str
    source_name: str
    published_at: datetime | None = None
    url: str | None = None


class BasketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str


class GeorgeIndexOut(BaseModel):
    basket_id: int
    basket_name: str
    george_index: float | None
    performance_1j: float | None
    performance_1s: float | None
    performance_1m: float | None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    pattern_id: int | None
    decision_type: str
    status: str
    entry_price: float
    take_profit: float | None
    stop_loss: float | None
    confidence: float
    rationale: str | None
    exit_scenario: str | None
    exit_volume_confirmed: bool | None
    exit_justification: str | None
    exit_proposed_at: datetime | None
    created_at: datetime


class ConfirmDecisionRequest(BaseModel):
    take_profit: float | None = None
    stop_loss: float | None = None


class AgentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_name: str
    description: str
    status: str
    symbol: str | None
    created_at: datetime
    context: dict


class CollectionTaskRequest(BaseModel):
    """Requête de déclenchement manuel d'une tâche de collecte (Phase 7,
    MVP) — voir `agents/orchestrator/run.py:run_collection_task`.
    `report_id` n'est utilisé (et requis) que pour `task_type="synthese_document"`."""

    task_type: str
    report_id: int | None = None


class CollectionTaskResponse(BaseModel):
    validated: list[AgentEventOut]
    quarantined_count: int


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class JaneAskRequest(BaseModel):
    question: str


class JaneAskResponse(BaseModel):
    answer: str


class ExplanationRequest(BaseModel):
    include_second_opinion: bool = False


class ExplanationResponse(BaseModel):
    explanation: str
    second_opinion: str | None = None


class JaneSecondOpinionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_id: int
    content: str
    created_at: datetime


class ReportRequest(BaseModel):
    basket_id: int | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    basket_id: int | None
    content: str
    created_at: datetime


class PortfolioCreateRequest(BaseModel):
    name: str
    decision_ids: list[int]


class PortfolioDecisionOut(DecisionOut):
    """`DecisionOut` + `quantity` — le nombre d'actions détenu dans *ce*
    portefeuille (colonne de la table de liaison `portfolio_decisions`, pas
    de `decisions` elle-même : une même décision peut avoir des quantités
    différentes dans deux portefeuilles distincts) — et `current_price`/
    `pnl_pct`/`price_updated_at`/`day_change_pct`, calculés à la volée depuis
    le prix le plus récent (pas des colonnes stockées), voir
    `api/routers/portfolios.py:_current_price_and_pnl`. `price_updated_at`
    est la date/heure de la dernière ingestion de prix pour ce titre, pas
    celle de la décision (`DecisionOut.created_at`, hérité). `day_change_pct`
    est l'évolution brute du cours par rapport à la séance précédente
    ((clôture du jour - clôture de la veille) / clôture de la veille) —
    volontairement *non* ajusté à la direction de la décision comme
    `pnl_pct` : c'est une lecture du marché ("le titre a bougé de X% hier"),
    pas un indicateur de performance de la position."""

    quantity: int | None = None
    current_price: float | None = None
    pnl_pct: float | None = None
    price_updated_at: datetime | None = None
    day_change_pct: float | None = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    decisions: list[PortfolioDecisionOut]
    total_pnl_amount: float | None = None  # somme des PnL en €, uniquement sur les lignes avec une quantité renseignée
    total_invested: float | None = None  # somme quantité × prix d'entrée, même périmètre que total_pnl_amount


class PriceRefreshStatus(BaseModel):
    """État du job de rafraîchissement des prix (voir api/routers/prices.py) —
    un seul job à la fois, exécuté en tâche de fond ; `total`/`updated_count`/
    `failed_symbols` ne sont renseignés qu'une fois `status == "done"`,
    `error` uniquement si `status == "failed"`."""

    status: Literal["idle", "running", "done", "failed"]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total: int | None = None
    updated_count: int | None = None
    failed_symbols: list[str] | None = None
    error: str | None = None


class AllocateBudgetRequest(BaseModel):
    budget: float


class AllocateBudgetResponse(BaseModel):
    portfolio: PortfolioOut
    summary: str


class CarryPairOut(BaseModel):
    """Une paire du panier Carry Trade (ad hoc, pas une phase du roadmap) et
    son score — voir `engine/carry_index.py`. Les champs de score restent
    `null` plutôt qu'une valeur fabriquée quand ils ne sont pas calculables
    (ex. historique de prix ou positionnement COT indisponible)."""

    symbol: str
    name: str
    funding_currency: str
    target_currency: str
    funding_rate_pct: float | None
    target_rate_pct: float | None
    carry_pct: float | None
    realized_vol_pct: float | None
    carry_vol_ratio: float | None
    cot_crowding_score: float | None
    decision: str


class CarryTradeDetailOut(CarryPairOut):
    """`CarryPairOut` + l'historique de prix récent (pour le graphique) —
    même schéma `PriceBarOut` que les actions, réutilisable tel quel par
    `CandlestickChart` côté web si besoin plus tard."""

    recent_prices: list[PriceBarOut]


class CarryTradeExplanationResponse(BaseModel):
    explanation: str


class CarryTradeRefreshResponse(BaseModel):
    fx_prices_updated: int
    fx_prices_failed: list[str]
    rates_updated: list[str]
    rates_failed: list[str]
    cot_updated: list[str]
    cot_failed: list[str]


class ShareEmailRequest(BaseModel):
    """`symbol` optionnel : présent uniquement pour les popups associées à un
    titre (ex. explication de décision) — voir `api/routers/share.py` pour ce
    que son absence implique (pas de graphique joint, texte seul).
    `take_profit`/`stop_loss` optionnels, tracés sur le graphique joint s'ils
    sont fournis — sans effet si `symbol` est absent (pas de graphique du
    tout dans ce cas)."""

    to_email: str
    subject: str
    text: str
    symbol: str | None = None
    take_profit: float | None = None
    stop_loss: float | None = None


class ShareEmailResponse(BaseModel):
    sent: bool
    chart_attached: bool
