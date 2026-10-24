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


class JaneSecondOpinion(Base):
    """Note de second avis de Jane pour une décision (`agents.jane.second_opinion`),
    persistée à chaque appel — jusqu'ici générée à la volée par
    `POST /decisions/{id}/explanation` et jamais conservée. Une table plutôt
    qu'une colonne sur `Decision` : le second avis peut être redemandé
    plusieurs fois pour la même décision au fil de son cycle de vie
    (proposée -> confirmée -> sortie), chaque appel garde sa propre trace
    plutôt que d'écraser la précédente.

    Objectif direct : permettre plus tard de corréler ces notes avec
    `DecisionOutcome.result`/`pnl_pct` (même `decision_id`) pour évaluer si
    le scepticisme de Jane prédit réellement de moins bonnes issues — non
    mesurable tant que ce texte n'était pas conservé nulle part."""

    __tablename__ = "jane_second_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


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


class JaneKnowledge(Base):
    """Base de connaissances méthodologiques/théoriques de Jane (Phase 7,
    rôle "veille méthodologique" — voir `agents/jane_knowledge.py` et
    `agents/jane_veille.py`), indexée par embedding comme `reports` mais un
    concept distinct de `pattern_candidates` : ici du savoir général
    (définition, méthodologie, mesure de performance...) réutilisé comme
    contexte RAG par `agents.jane.second_opinion`, jamais une figure
    chartiste candidate à backtester.

    Amorcée une fois avec le contenu de `Jane_Synthese_Connaissances.md`
    (voir `agents/jane_knowledge.py:seed_from_markdown`), puis alimentée en
    continu par `agents/jane_veille.py`."""

    __tablename__ = "jane_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    principe que `BondYieldSnapshot` (Obligataire Watch) et
    `CompanyFundamentals` (yfinance) déjà présents dans ce fichier.

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


class EnergyPriceSnapshot(Base):
    """Instantané quotidien du marché de l'énergie via OilPriceAPI
    (`ingestion/energy_prices.py`) — ad hoc, pas une phase du roadmap.
    Brent, WTI, gaz naturel, et produits raffinés (diesel, fioul
    domestique, essence). Même principe que `CompanyFundamentals` (yfinance)
    juste au-dessus : une ligne par (matière première, jour d'ingestion),
    jamais écrasée, pour qu'un vrai historique s'accumule dans le temps.

    `commodity_code` reprend directement le code OilPriceAPI (ex.
    `"BRENT_CRUDE_USD"`) plutôt qu'une nouvelle taxonomie. `snapshot_date`
    est la date du jour d'ingestion (`date.today()`), pas la date
    d'observation du cours lui-même (`price_observed_at`, qui peut être
    légèrement en retard un week-end/jour férié de marché fermé) — la clé
    unique porte sur `snapshot_date` pour garantir un import quotidien
    idempotent (une seule ligne par jour même si le job est relancé)."""

    __tablename__ = "energy_price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commodity_code: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    change_24h_pct: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    price_observed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    snapshot_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("commodity_code", "snapshot_date", name="uq_energy_price_snapshot_commodity_date"),
    )


class CompanyFundamentals(Base):
    """Instantané quotidien des données fondamentales/entreprise d'un titre
    (`ingestion/fundamentals.py`, via yfinance `Ticker.info`) — ad hoc, pas
    une phase du roadmap. Contrairement à une table qui ne garde que la
    dernière valeur connue par clé (écrasée à chaque collecte), chaque exécution
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
    par (titre, date ex-dividende) pour une ingestion quotidienne idempotente."""

    __tablename__ = "dividends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    ex_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)

    __table_args__ = (UniqueConstraint("symbol", "ex_date", name="uq_dividend_symbol_ex_date"),)


class PriceHistoryLong(Base):
    """Historique de prix long terme par titre (`ingestion/price_history.py`,
    via yfinance `period="10y"`) — ad hoc, pas une phase du roadmap. Table
    dédiée, distincte de `prices_ohlcv` (qui ne garde que 2 ans, la fenêtre
    utilisée par la détection de figures, Phase 1) : demandé directement par
    l'utilisateur pour disposer de 6 mois/1 an/3 ans/5 ans/10 ans de recul.
    Une seule ligne par (titre, séance) couvrant les 10 ans, plutôt que 5
    lignes redondantes par durée demandée — 10 ans contient déjà les 4 autres
    durées, filtrables à la demande sur `ts` plutôt que stockées 5 fois."""

    __tablename__ = "price_history_long"

    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Numeric, nullable=False)
    high: Mapped[float] = mapped_column(Numeric, nullable=False)
    low: Mapped[float] = mapped_column(Numeric, nullable=False)
    close: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CompanyNewsKnowledge(Base):
    """Base de connaissances d'actualités entreprises pour George (ad hoc,
    pas une phase du roadmap — demandé directement par l'utilisateur : que
    George mette à jour ses connaissances en continu, scopé aux entreprises
    CAC 40/Mid Cac 60 déjà suivies plus le secteur biocarburants/gaz
    renouvelables). Même principe indexé-par-embedding que `JaneKnowledge`,
    alimentée en continu par `agents/george_veille.py`, mais scopée par
    entreprise (`company_name`/`symbol`) plutôt que par sujet méthodologique
    général — consommée par `agents.chat.answer_question` en complément de
    l'analyse quantitative pour les titres suivis, et à la place du repli
    web à la volée pour les entreprises biocarburants/gaz renouvelables déjà
    couvertes ici.

    `symbol` est nullable et volontairement SANS clé étrangère vers
    `securities.symbol` : les entreprises du secteur biocarburants/gaz
    renouvelables ciblées ici n'y ont pour la plupart aucune ligne — une
    FK stricte casserait l'ingestion dès la première entreprise hors
    univers suivi."""

    __tablename__ = "company_news_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class GeopoliticalKnowledge(Base):
    """Base de connaissances d'actualités géopolitiques/économiques par pays
    (Phase 7, "pilier 7" du roadmap — voir `whitelist_journaux.md`/`.json`,
    jusqu'ici jamais exploités par aucun code) — ad hoc dans sa réalisation
    concrète (recherche Tavily + synthèse Mistral, pas l'orchestrateur
    LangGraph/Celery/scraping prévu par le roadmap complet). Même principe
    indexé-par-embedding que `CompanyNewsKnowledge` juste au-dessus, alimenté
    en continu par `agents/geopolitical_veille.py`, mais scopé par pays
    (`country`/`region`) plutôt que par entreprise — consommé par
    `agents.chat.answer_question` en complément de l'analyse quantitative
    (un investisseur demandant "quel est le risque géopolitique en Russie ?"
    obtient une vraie synthèse plutôt qu'un silence, sans jamais faire dire à
    George qu'il détecte lui-même un risque chiffré).

    `region` (Europe & UK, Amérique du Nord & Latine, Asie...) vient de
    `agents/geopolitical_veille.py:COUNTRY_TO_REGION` — PAS de
    `whitelist_journaux.md`/`.json` eux-mêmes, qui n'ont aucune colonne
    région (une seule table plate par pays). Texte libre, pas un enum, même
    choix que `CompanyFundamentals.sector` pour rester tolérant aux libellés
    changeants d'une source de référence externe."""

    __tablename__ = "geopolitical_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    region: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


# Codes stables identifiant chaque instrument obligataire suivi (Obligataire
# Watch, ad hoc, pas une phase du roadmap) — utilisés comme clé dans
# BondYieldSnapshot/BondAlertThreshold/BondAlertEvent plutôt que le libellé
# français affiché (qui peut changer sans casser les requêtes/jointures).
BOND_INSTRUMENT_OAT_FR_10Y = "OAT_FR_10Y"
BOND_INSTRUMENT_BUND_DE_10Y = "BUND_DE_10Y"
BOND_INSTRUMENT_UST_US_10Y = "UST_US_10Y"
BOND_INSTRUMENT_UST_US_2Y = "UST_US_2Y"

# Pseudo-instrument : jamais une ligne de `BondYieldSnapshot` (ce n'est pas
# une valeur directement observée chez une source externe, mais calculée à
# partir de OAT_FR_10Y/BUND_DE_10Y) — reconnu spécifiquement par
# `engine/bond_alerts.py:latest_value_by_instrument` pour pouvoir configurer
# un seuil d'alerte dessus comme pour un instrument normal.
BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS = "SPREAD_OAT_BUND_BPS"


class BondYieldSnapshot(Base):
    """Observation d'un rendement obligataire (Obligataire Watch, ad hoc,
    pas une phase du roadmap) — `ingestion/bond_yields.py`. `instrument` est
    un des `BOND_INSTRUMENT_*` ci-dessus, pas de FK vers `securities` : un
    rendement souverain n'est pas un titre coté qui y aurait une ligne.

    `observed_at`/`fetched_at` sont délibérément distincts (demandé
    explicitement par le cahier des charges) : la date de la cotation n'est
    pas celle de la collecte — des séries FRED/OCDE mensuelles peuvent être
    collectées plusieurs jours après leur publication réelle. Unique sur
    (instrument, observed_at) pour une ingestion idempotente."""

    __tablename__ = "bond_yield_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(Text, nullable=False)
    value_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    observed_at: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("instrument", "observed_at", name="uq_bond_yield_snapshot_instrument_date"),)


class BondAlertThreshold(Base):
    """Seuil d'alerte configurable pour un instrument obligataire
    (Obligataire Watch) — modifiable via l'API sans toucher au code, comme
    demandé explicitement par le cahier des charges. `direction` : "above"
    (alerte si value_pct dépasse threshold_pct) ou "below" (alerte si
    value_pct passe sous threshold_pct) — les deux franchissements prévus
    par le cahier des charges (hausse et retour sous le seuil) sont deux
    lignes distinctes, pas un seul seuil bidirectionnel ambigu.

    `threshold_pct` : nom conservé par cohérence avec `BondYieldSnapshot
    .value_pct`, mais pour `BOND_INSTRUMENT_SPREAD_OAT_BUND_BPS` cette
    colonne contient une valeur en **points de base**, pas en pourcentage
    (ex. 150 pour "150 pb") — `engine/bond_alerts.py` compare toujours la
    même unité des deux côtés pour cet instrument, jamais de confusion
    pourcentage/points de base dans la comparaison elle-même."""

    __tablename__ = "bond_alert_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)  # "above" | "below"
    threshold_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("instrument", "direction", name="uq_bond_alert_threshold_instrument_direction"),)


class BondAlertEvent(Base):
    """Franchissement de seuil effectivement détecté (Obligataire Watch) —
    `engine/bond_alerts.py`. `status` ("triggered" | "resolved") permet de
    savoir si le seuil est toujours franchi ou si la valeur est repassée du
    bon côté, sans dupliquer deux tables alertes actives/historique. Pas de
    ligne nouvelle à chaque cycle de collecte tant que le statut n'a pas
    changé — c'est exactement la "prévention des alertes répétitives
    inutiles" demandée par le cahier des charges : un seuil resté franchi
    10 jours de suite ne produit qu'un seul événement "triggered", pas 10."""

    __tablename__ = "bond_alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_id: Mapped[int] = mapped_column(ForeignKey("bond_alert_thresholds.id"), nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    observed_value_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # "triggered" | "resolved"
    triggered_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)


class BondCollectionRun(Base):
    """Journal d'exécution du collecteur Obligataire Watch
    (`ingestion/bond_yields.py`) — visibilité explicite des erreurs de
    collecte demandée par le cahier des charges (critère d'acceptation V1
    §17.7), même esprit que `CollectionRun` n'existant nulle part ailleurs
    dans Georges : les autres collecteurs ad hoc (fondamentaux, etc.) n'ont
    pas ce besoin exprimé explicitement, celui-ci l'a."""

    __tablename__ = "bond_collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # "running" | "success" | "partial" | "failed"
    instruments_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    instruments_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class StrategicReport(Base):
    """Rapport stratégique hebdomadaire (ad hoc, pas une phase du roadmap) —
    `agents/strategic_report.py`, généré à la demande depuis l'onglet
    « Rapport » (web et mobile). Deux parties stockées séparément, par
    construction anti-hallucination :
    - `data` : tout ce qui est chiffré et calculé en Python (taux, spread,
      Brent, indice CAC 40, indicateur de risque, tableau des 40 valeurs,
      portefeuille virtuel, sources web numérotées) — jamais produit par un LLM ;
    - `narrative_markdown` : le commentaire rédigé par le LLM à partir de ce
      seul contexte, qui ne peut citer que les chiffres présents dans `data`
      ou dans les extraits web numérotés de `data["sources"]`.
    `risk_level` est dupliqué hors de `data` pour lister l'historique sans
    charger le JSON complet."""

    __tablename__ = "strategic_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)  # "vert" | "orange" | "rouge" | "indetermine"
    narrative_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)


class VirtualPortfolioTrade(Base):
    """Ordre simulé du portefeuille virtuel du rapport stratégique (capital
    initial 100 000 €, `engine/virtual_portfolio.py`). Jamais envoyé à un
    courtier. L'état du portefeuille (positions, liquidités) est toujours
    recalculé à partir de la suite complète des ordres, jamais stocké à part,
    pour qu'il ne puisse pas diverger de son propre historique."""

    __tablename__ = "virtual_portfolio_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategic_reports.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("securities.symbol"), nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)  # "achat" | "vente"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    fees: Mapped[float] = mapped_column(Numeric, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class VirtualPortfolioSnapshot(Base):
    """Valorisation du portefeuille virtuel au moment d'un rapport — sert à
    calculer la performance d'un rapport à l'autre sans revaloriser le passé
    avec des prix d'aujourd'hui."""

    __tablename__ = "virtual_portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("strategic_reports.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    valued_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric, nullable=False)
    positions_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    fees_total: Mapped[float] = mapped_column(Numeric, nullable=False)
