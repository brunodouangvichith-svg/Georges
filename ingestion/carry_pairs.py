"""Charge l'univers de paires de devises suivies pour le panier Carry Trade
(ad hoc, pas une phase du roadmap) dans `currency_pairs`.

Usage :
    python -m ingestion.carry_pairs

Liste volontairement fixe pour cette V1 (pas de système de paniers FX
multiples/génériques) — les 6 paires du prototype fourni par l'utilisateur,
toutes vérifiées vivantes sur yfinance avant l'écriture de ce fichier
(`yf.Ticker(symbol).history(period="5d")` non vide pour chacune)."""

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ingestion.db import get_engine
from ingestion.models import CurrencyPair

# (symbol yfinance, nom, devise de financement, devise cible)
CARRY_PAIRS = [
    ("MXNJPY=X", "Peso mexicain / Yen japonais", "JPY", "MXN"),
    ("AUDJPY=X", "Dollar australien / Yen japonais", "JPY", "AUD"),
    ("NZDJPY=X", "Dollar néo-zélandais / Yen japonais", "JPY", "NZD"),
    ("GBPJPY=X", "Livre sterling / Yen japonais", "JPY", "GBP"),
    ("USDJPY=X", "Dollar américain / Yen japonais", "JPY", "USD"),
    ("EURCHF=X", "Euro / Franc suisse", "CHF", "EUR"),
]


def seed_currency_pairs() -> int:
    engine = get_engine()
    rows = [
        {"symbol": symbol, "name": name, "funding_currency": funding, "target_currency": target}
        for symbol, name, funding, target in CARRY_PAIRS
    ]
    with engine.begin() as conn:
        stmt = pg_insert(CurrencyPair).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CurrencyPair.symbol],
            set_={
                "name": stmt.excluded.name,
                "funding_currency": stmt.excluded.funding_currency,
                "target_currency": stmt.excluded.target_currency,
            },
        )
        conn.execute(stmt)
    return len(rows)


if __name__ == "__main__":
    count = seed_currency_pairs()
    print(f"{count} paires chargées dans currency_pairs.")
