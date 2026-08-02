from __future__ import annotations

import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, BigInteger, Text, UniqueConstraint, func
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
    """Table Postgres classique (plus une hypertable TimescaleDB depuis
    l'hébergement sur Supabase, voir CLAUDE.md) — une ligne par (titre, horodatage)."""

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
    dans le flux d'activité de `web/`. Depuis le MVP de la Phase 7
    (`agents/orchestrator/`), une ligne validée ici est écrite par
    `run_collection_task` — `agent_name` identifie le sous-agent producteur,
    ce qui joue le même rôle qu'un `produced_by_agent` séparé sans ajouter de
    colonne redondante. Les infos non validées vont dans
    `CollectedInfoQuarantine` plutôt qu'ici."""

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


class CollectedInfoQuarantine(Base):
    """Info collectée par un sous-agent (Phase 7) mais dont la validation a
    échoué — recoupement multi-sources contradictoire (`agents/orchestrator
    /validation.py:validate`). `payload` porte les valeurs par source qui se
    contredisent ; `reason` explique le rejet en une phrase. Une info à
    source unique ne passe jamais ici (elle est `validated` par défaut, voir
    `validate`) — cette table n'existe que pour les vrais désaccords entre
    au moins deux sources indépendantes."""

    __tablename__ = "collected_info_quarantine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(ForeignKey("securities.symbol"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


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
    peuvent contenir la même décision). `quantity` (nombre entier d'actions)
    n'est pas renseigné à la création — rempli soit à la main, soit par
    `POST /portfolios/{id}/allocate` (répartition d'un budget, voir
    `engine/portfolio_allocation.py`)."""

    __tablename__ = "portfolio_decisions"

    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), primary_key=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MacroIndicatorSnapshot(Base):
    """Instantané d'un indicateur numérique collecté par un sous-agent de
    veille (Phase 7 : `agents/collectors/macro.py` — taux OAT 10 ans,
    EUR/USD, EUR/GBP, EUR/CHF ; `eurostat.py` — chômage, inflation HICP ;
    `tic.py` — détention de Treasuries US par la France) — ad hoc, pas une
    phase du roadmap. Remplace l'écriture uniquement dans `agent_events`/
    `collected_info_quarantine` (toujours faite en parallèle, pour le flux
    d'activité) par une vraie table interrogeable dans le temps, même
    principe que `CarryRateSnapshot`/`CotPositioning` (panier Carry Trade)
    et `CompanyFundamentals` (yfinance) déjà présents dans ce fichier.

    `indicator` réutilise directement le `label` déjà défini dans chaque
    collecteur (ex. "Taux de change EUR/USD") plutôt que d'inventer une
    nouvelle taxonomie de slugs. `observed_at` reste du texte libre, pas une
    vraie `Date` : le format varie selon la source (FRED : date ISO
    complète ; Eurostat/TIC : simple période/mois) — même type que
    `agents/orchestrator/types.py:CollectedItem.observed_at`, jamais
    reparsé. Unique par (indicateur, source, date observée), pas juste
    (indicateur, date) : un indicateur comme EUR/USD a plusieurs sources
    indépendantes par cycle (FRED, BCE, Frankfurter) et chacune garde sa
    propre valeur plutôt que de s'écraser mutuellement. Seuls les groupes
    **validés** (jamais une quarantaine) sont écrits ici, voir
    `agents/orchestrator/run.py:NUMERIC_INDICATOR_TASK_TYPES`."""

    __tablename__ = "macro_indicator_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    reliability_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("indicator", "source_name", "observed_at", name="uq_macro_indicator_snapshot"),
    )


class CurrencyPair(Base):
    """Univers des paires de devises suivies pour le panier Carry Trade (ad
    hoc, pas une phase du roadmap) — schéma FX dédié plutôt qu'une
    réutilisation de `Security`, dont `country`/`sector` (NOT NULL) n'ont
    aucun sens pour une paire de devises. `symbol` est le ticker yfinance
    (ex. `"AUDJPY=X"`)."""

    __tablename__ = "currency_pairs"

    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    funding_currency: Mapped[str] = mapped_column(Text, nullable=False)  # devise vendue/empruntée, ex. "JPY"
    target_currency: Mapped[str] = mapped_column(Text, nullable=False)  # devise achetée/investie, ex. "AUD"


class FxPriceOHLCV(Base):
    """Table Postgres classique (plus une hypertable TimescaleDB, voir
    `PriceOHLCV` ci-dessus) — historique quotidien d'une paire de devises
    (`ingestion/fx_rates.py`, via yfinance). Même forme que `PriceOHLCV`
    mais FK vers `currency_pairs` — `volume` vaut toujours 0 pour le FX spot
    (yfinance n'en fournit pas de réel), conservé pour rester dans la même
    forme que `PriceOHLCV` plutôt que de retirer la colonne pour ce seul cas."""

    __tablename__ = "fx_prices_ohlcv"

    symbol: Mapped[str] = mapped_column(ForeignKey("currency_pairs.symbol"), primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Numeric, nullable=False)
    high: Mapped[float] = mapped_column(Numeric, nullable=False)
    low: Mapped[float] = mapped_column(Numeric, nullable=False)
    close: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CarryRateSnapshot(Base):
    """Dernier taux court connu par devise (`ingestion/carry_rates.py`,
    FRED) — pas de FK vers `securities`/`currency_pairs` (une devise, pas un
    titre ni une paire) : réutiliser `AgentEvent.symbol` était tentant mais
    porte une contrainte de clé étrangère vers `securities.symbol`, où une
    devise n'a pas sa place (même piège que le collecteur Finnhub, voir
    CLAUDE.md). Unique par (devise, date d'observation) pour une ingestion
    idempotente."""

    __tablename__ = "carry_rate_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # code ISO 3 lettres, ex. "JPY"
    rate_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    observed_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("currency", "observed_at", name="uq_carry_rate_snapshot_currency_date"),)


class CompanyFundamentals(Base):
    """Instantané quotidien des données fondamentales/entreprise d'un titre
    (`ingestion/fundamentals.py`, via yfinance `Ticker.info`) — ad hoc, pas
    une phase du roadmap. Contrairement à `CarryRateSnapshot`/`CotPositioning`
    (une seule ligne "dernière valeur connue" par clé), chaque exécution
    quotidienne insère une nouvelle ligne plutôt que d'écraser la
    précédente : les fondamentaux évoluent lentement mais un vrai historique
    (ex. évolution du PE ou du market cap dans le temps) a de la valeur, pas
    seulement le dernier instantané. Toutes les colonnes de contenu sont
    nullable : la couverture yfinance est bonne sur cet univers (vérifié en
    direct, contrairement au vrai trou de couverture Finnhub déjà découvert
    sur les mêmes tickers `.PA`, voir CLAUDE.md) mais pas garantie champ par
    champ. `raw_info` conserve le dict `Ticker.info` complet — même principe
    que `PatternDetected.context`/`CollectedInfoQuarantine.payload` : capture
    tout ce qui n'a pas sa propre colonne, pour un usage futur sans nouvelle
    migration."""

    __tablename__ = "company_fundamentals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    observed_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    exchange: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_business_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_time_employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trailing_pe: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    forward_pe: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    beta: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fifty_two_week_high: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    fifty_two_week_low: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    raw_info: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (UniqueConstraint("symbol", "observed_at", name="uq_company_fundamentals_symbol_date"),)


class Dividend(Base):
    """Un versement de dividende par ligne (`ingestion/fundamentals.py`, via
    yfinance `Ticker.dividends`) — ad hoc, pas une phase du roadmap. Unique
    par (titre, date ex-dividende) pour une ingestion quotidienne idempotente
    (même précédent que `CarryRateSnapshot`/`CotPositioning`)."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    ex_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (UniqueConstraint("symbol", "ex_date", name="uq_dividend_symbol_ex_date"),)


class CotPositioning(Base):
    """Dernier positionnement spéculatif connu par devise (rapport CFTC
    "TFF — Futures Only", `ingestion/cot_positioning.py`) — `lev_money_long`/
    `lev_money_short` sont les positions "Leveraged Funds" (l'équivalent TFF
    des spéculateurs). Unique par (devise, date du rapport) pour une
    ingestion idempotente."""

    __tablename__ = "cot_positioning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    report_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    lev_money_long: Mapped[int] = mapped_column(Integer, nullable=False)
    lev_money_short: Mapped[int] = mapped_column(Integer, nullable=False)
    open_interest_all: Mapped[int] = mapped_column(Integer, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("currency", "report_date", name="uq_cot_positioning_currency_date"),)
