from __future__ import annotations

import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, BigInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 1024  # dimension de sortie du modèle mistral-embed (Phase 4)


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
    """Décision proposée par George pour un titre (jamais exécutée
    automatiquement). `status` (Phase 6) trace son cycle de vie :
    'proposee' (créée par `engine.propose_decisions`, niveaux non encore
    validés) -> 'confirmee' (niveaux validés par l'investisseur) ->
    'sortie_proposee' (le job de suivi a détecté un franchissement de
    take-profit/stop-loss et propose un scénario de sortie, voir les
    colonnes `exit_*`) -> 'cloturee' (sortie confirmée, résultat enregistré
    dans `decision_outcomes`). Les décisions illustratives pré-existantes
    (`ingestion/seed_demo.py`) sont rétroactivement 'confirmee' (elles
    étaient déjà présentées comme définitives avant que ce cycle n'existe).
    `pattern_id` rattache explicitement une décision à la figure qui l'a
    motivée — avant la Phase 6, ce lien n'existait pas et devait être
    reconstitué par heuristique (voir `agents/explainer.py:find_pattern_for_decision`,
    conservée comme repli pour les décisions illustratives sans `pattern_id`)."""

    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    pattern_id: Mapped[int | None] = mapped_column(ForeignKey("patterns_detected.id"), nullable=True)
    decision_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    take_profit: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_scenario: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_volume_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    exit_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_proposed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
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


class Report(Base):
    """Rapport texte généré automatiquement (portefeuille ou panier, Phase 4)
    — voir `agents/reports.py`. `embedding` indexe le contenu via pgvector
    pour la recherche sémantique (tâche 4 de la Phase 4), en complément des
    requêtes SQL directes utilisées par `/chat`."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)  # "portfolio" ou "basket:<id>"
    basket_id: Mapped[int | None] = mapped_column(ForeignKey("baskets.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class AgentEvent(Base):
    """Ligne d'activité d'un sous-agent de veille (Phase 7), au format
    carnet d'ordres consommé par `GET /agents/activity` (Phase 3) et affiché
    dans le flux d'activité de `web/`. Aucun sous-agent n'existe encore pour
    l'alimenter — table créée en avance, comme `pattern_candidates`."""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # validated | pending | quarantine
    symbol: Mapped[str | None] = mapped_column(ForeignKey("securities.symbol"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class Portfolio(Base):
    """Portefeuille nommé, choisi manuellement par l'investisseur à partir
    d'un sous-ensemble de `decisions` (web/, écran « Mon Portefeuille ») —
    distinct du `Report` de portée `"portfolio"` (Phase 4), qui désigne lui
    l'ensemble du parc suivi, pas une sélection personnelle. Persisté côté
    base plutôt qu'en localStorage pour survivre au-delà du navigateur qui
    l'a créé (aucun système de comptes n'existe encore, voir Phase 9 — ce
    n'est donc pas *le* portefeuille d'un utilisateur identifié, juste une
    liste nommée partagée par tous les clients de l'API à ce stade)."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class PortfolioDecision(Base):
    """Table de liaison portefeuille <-> décision (plusieurs portefeuilles
    peuvent contenir la même décision)."""

    __tablename__ = "portfolio_decisions"

    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), primary_key=True)
