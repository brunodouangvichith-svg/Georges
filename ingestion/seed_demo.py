"""Seed de démonstration (Phase 3) : paniers par secteur, quelques décisions
et événements d'agents illustratifs — pour qu'un dashboard `web/` branché
sur l'API réelle ait quelque chose à afficher sans attendre les Phases 6/7,
qui créeront ces données en production.

Contrairement à `ingestion.seed` (univers CAC 40, données réelles), ce
script insère des données **explicitement fictives/illustratives** — à ne
pas confondre avec de vraies décisions d'investissement. Sans danger à
relancer : chaque étape vérifie ce qui existe déjà avant d'insérer.

Usage :
    python -m ingestion.seed_demo
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import AgentEvent, Basket, BasketSecurity, Decision, PriceHistoryLong, Security

# (symbol, decision_type, take_profit_pct, stop_loss_pct, confidence, rationale)
DEMO_DECISIONS = [
    ("AIR.PA", "Achat", 0.08, -0.05, 78.0, "Démonstration — carnet de commandes pluriannuel (illustratif)."),
    ("MC.PA", "Surveiller", 0.06, -0.04, 55.0, "Démonstration — demande chinoise à confirmer (illustratif)."),
    ("SAN.PA", "Renforcer", 0.05, -0.04, 66.0, "Démonstration — pipeline R&D porteur (illustratif)."),
]

# (agent_name, description, status, symbol | None)
DEMO_AGENT_EVENTS = [
    ("presse energie", "Notes analystes Brent — 3 sources recoupées", "validated", None),
    ("macro FRED", "Taux OAT 10 ans mis à jour", "validated", None),
    ("resultats", "Calendrier T3 relevé pour le panier Finance", "validated", None),
    ("presse sect.", "Rumeur non confirmée sur un contrat export", "quarantine", "AIR.PA"),
    ("reglementaire", "Dépôt SEC en cours d'analyse", "pending", "SAN.PA"),
]


def seed_baskets_by_sector(engine) -> int:
    """Un panier par secteur distinct parmi `securities`, avec tous les
    titres de ce secteur en équipondération. Idempotent (upsert sur le nom
    du panier, `on_conflict_do_nothing` sur les liens)."""
    with engine.begin() as conn:
        securities = conn.execute(select(Security.symbol, Security.sector)).all()

    sectors = sorted({s.sector for s in securities})

    with engine.begin() as conn:
        for sector in sectors:
            stmt = pg_insert(Basket).values(name=sector, type="secteur")
            stmt = stmt.on_conflict_do_nothing(index_elements=[Basket.name])
            conn.execute(stmt)

        basket_ids = {row.name: row.id for row in conn.execute(select(Basket.id, Basket.name))}

        links = [
            {"basket_id": basket_ids[s.sector], "symbol": s.symbol, "weight": None}
            for s in securities
            if s.sector in basket_ids
        ]
        if links:
            stmt = pg_insert(BasketSecurity).values(links)
            stmt = stmt.on_conflict_do_nothing(index_elements=[BasketSecurity.basket_id, BasketSecurity.symbol])
            conn.execute(stmt)

    return len(sectors)


def _latest_close(engine, symbol: str) -> float | None:
    with engine.begin() as conn:
        row = conn.execute(
            select(PriceHistoryLong.close)
            .where(PriceHistoryLong.symbol == symbol)
            .order_by(PriceHistoryLong.ts.desc())
            .limit(1)
        ).first()
    return float(row.close) if row else None


def seed_demo_decisions(engine) -> int:
    """N'invente jamais de prix : une décision de démonstration n'est
    insérée que si `price_history_long` a déjà un historique pour ce titre
    (`python -m ingestion.price_history`) — repointé depuis `prices_ohlcv`
    en même temps que le reste du moteur (voir CLAUDE.md). Ignore les titres
    ayant déjà une décision, pour rester sans danger à relancer."""
    with engine.begin() as conn:
        existing_symbols = {row[0] for row in conn.execute(select(Decision.symbol).distinct())}

    inserted = 0
    for symbol, decision_type, tp_pct, sl_pct, confidence, rationale in DEMO_DECISIONS:
        if symbol in existing_symbols:
            continue
        entry = _latest_close(engine, symbol)
        if entry is None:
            continue
        with engine.begin() as conn:
            conn.execute(
                Decision.__table__.insert().values(
                    symbol=symbol,
                    decision_type=decision_type,
                    entry_price=entry,
                    take_profit=round(entry * (1 + tp_pct), 2),
                    stop_loss=round(entry * (1 + sl_pct), 2),
                    confidence=confidence,
                    rationale=rationale,
                )
            )
        inserted += 1
    return inserted


def seed_demo_agent_events(engine) -> int:
    """N'insère le lot de démonstration qu'une seule fois (si la table est
    vide) — `agent_events` n'a pas de clé naturelle sur laquelle upserter."""
    with engine.begin() as conn:
        if conn.execute(select(AgentEvent.id).limit(1)).first() is not None:
            return 0
        for agent_name, description, status, symbol in DEMO_AGENT_EVENTS:
            conn.execute(
                AgentEvent.__table__.insert().values(
                    agent_name=agent_name,
                    description=description,
                    status=status,
                    symbol=symbol,
                    context={},
                )
            )
    return len(DEMO_AGENT_EVENTS)


def run() -> dict[str, int]:
    engine = get_engine()
    return {
        "baskets": seed_baskets_by_sector(engine),
        "decisions": seed_demo_decisions(engine),
        "agent_events": seed_demo_agent_events(engine),
    }


if __name__ == "__main__":
    summary = run()
    print(
        f"{summary['baskets']} paniers (par secteur), "
        f"{summary['decisions']} décisions de démonstration, "
        f"{summary['agent_events']} événements d'agents insérés."
    )
