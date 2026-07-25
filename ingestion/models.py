from __future__ import annotations

import datetime

from sqlalchemy import ForeignKey, Integer, Numeric, BigInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Security(Base):
    """Univers de titres suivis (référentiel), voir aussi `ingestion/cac40.py`."""

    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str] = mapped_column(Text, nullable=False)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)


class PriceOHLCV(Base):
    """Hypertable TimescaleDB — une ligne par (titre, horodatage)."""

    __tablename__ = "prices_ohlcv"

    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Numeric, nullable=False)
    high: Mapped[float] = mapped_column(Numeric, nullable=False)
    low: Mapped[float] = mapped_column(Numeric, nullable=False)
    close: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)


class PatternDetected(Base):
    """Figure chartiste détectée par le moteur (Phase 1)."""

    __tablename__ = "patterns_detected"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    pattern_type: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Decision(Base):
    """Décision proposée par George pour un titre (jamais exécutée automatiquement)."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class DecisionOutcome(Base):
    """Résultat réel d'une décision, évalué après coup (Phase 2)."""

    __tablename__ = "decision_outcomes"

    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), primary_key=True)
    evaluated_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Numeric, nullable=False)


class Basket(Base):
    """Panier thématique/géographique/sectoriel utilisé pour agréger le
    George Index (Phase 2) — voir `engine/george_index.md`."""

    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # pays | devise | secteur | theme


class BasketSecurity(Base):
    """Table de liaison panier <-> titre, avec un poids optionnel (sinon
    équipondération au sein du panier)."""

    __tablename__ = "basket_securities"

    basket_id: Mapped[int] = mapped_column(ForeignKey("baskets.id"), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), primary_key=True)
    weight: Mapped[float | None] = mapped_column(Numeric, nullable=True)


class PatternCandidate(Base):
    """Même forme que `patterns_detected`, mais pour les figures proposées
    par l'agent de veille méthodologique (Phase 7) : elles sont backtestées
    ici avant toute promotion éventuelle vers le catalogue actif des
    détecteurs de `engine/patterns/`. Aucun code ne les promeut encore
    automatiquement — cette table n'est pour l'instant qu'un espace
    d'atterrissage/backtesting manuel."""

    __tablename__ = "pattern_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    pattern_type: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
