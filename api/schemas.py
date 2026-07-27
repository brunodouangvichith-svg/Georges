"""Schémas Pydantic de réponse de l'API (Phase 3).

Toutes les listes sont enveloppées dans le même schéma générique de
pagination (`Page[T]`) : `{"items": [...], "total": N, "limit": L, "offset": O}`.
"""

from datetime import datetime
from typing import Generic, TypeVar

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


class BasketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str


class GeorgeIndexOut(BaseModel):
    basket_id: int
    basket_name: str
    george_index: float | None


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


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str


class ExplanationRequest(BaseModel):
    include_second_opinion: bool = False


class ExplanationResponse(BaseModel):
    explanation: str
    second_opinion: str | None = None


class ReportRequest(BaseModel):
    basket_id: int | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope: str
    basket_id: int | None
    content: str
    created_at: datetime
