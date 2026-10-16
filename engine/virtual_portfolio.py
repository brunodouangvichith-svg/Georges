"""Portefeuille virtuel du rapport stratégique (ad hoc, pas une phase du
roadmap) — pur, sans base ni réseau. Calcul d'argent déterministe en Python,
jamais confié au LLM (même principe que `engine/portfolio_allocation.py`).

Règles, volontairement simples et lisibles :
- capital initial `INITIAL_CAPITAL`, frais simulés `FEE_RATE` du montant brut
  de chaque ordre (achat comme vente), quantités entières arrondies vers le bas ;
- l'état (positions, liquidités, frais cumulés) est **toujours recalculé à
  partir de la suite complète des ordres** (`holdings_from_trades`) ;
- univers : les valeurs du CAC 40 ; signal = la décision ouverte la plus
  récente de George pour chaque valeur (`Achat`/`Renforcer` = haussier,
  `Surveiller` = neutre, autre = baissier) ;
- ventes d'abord : toute position dont le signal est devenu baissier est
  vendue en totalité ; une position sans signal ou au signal neutre est
  conservée ;
- puis achats : signaux haussiers non détenus, par confiance décroissante,
  `TARGET_POSITION_WEIGHT` de la valeur totale chacun, tant qu'il reste des
  liquidités au-dessus de la réserve minimale (`MIN_CASH_BY_RISK`, plus
  élevée quand le risque obligataire monte) et moins de `MAX_POSITIONS` ;
- jamais de renforcement d'une position existante ni de vente partielle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

INITIAL_CAPITAL = 100_000.0
FEE_RATE = 0.0015
TARGET_POSITION_WEIGHT = 0.07
MAX_POSITIONS = 12
MIN_CASH_BY_RISK = {"vert": 0.30, "orange": 0.45, "rouge": 0.60, "indetermine": 0.45}

BULLISH_DECISIONS = {"Achat", "Renforcer"}
NEUTRAL_DECISIONS = {"Surveiller"}


@dataclass
class Holdings:
    cash: float = INITIAL_CAPITAL
    positions: dict[str, int] = field(default_factory=dict)
    fees_total: float = 0.0


@dataclass
class Signal:
    symbol: str
    decision_type: str
    confidence: float


@dataclass
class PlannedTrade:
    symbol: str
    side: str  # "achat" | "vente"
    quantity: int
    price: float
    fees: float
    rationale: str

    @property
    def gross(self) -> float:
        return self.quantity * self.price


def fee_for(gross: float) -> float:
    return round(gross * FEE_RATE, 2)


def holdings_from_trades(trades: list[dict]) -> Holdings:
    """`trades` : ordres passés dans l'ordre chronologique, chacun
    `{"symbol", "side", "quantity", "price", "fees"}`."""
    holdings = Holdings()
    for trade in trades:
        gross = trade["quantity"] * float(trade["price"])
        fees = float(trade["fees"])
        held = holdings.positions.get(trade["symbol"], 0)
        if trade["side"] == "achat":
            holdings.cash -= gross + fees
            holdings.positions[trade["symbol"]] = held + trade["quantity"]
        elif trade["side"] == "vente":
            holdings.cash += gross - fees
            remaining = held - trade["quantity"]
            if remaining > 0:
                holdings.positions[trade["symbol"]] = remaining
            else:
                holdings.positions.pop(trade["symbol"], None)
        else:
            raise ValueError(f"Sens d'ordre inconnu : {trade['side']!r}")
        holdings.fees_total += fees
    holdings.cash = round(holdings.cash, 2)
    holdings.fees_total = round(holdings.fees_total, 2)
    return holdings


def positions_value(positions: dict[str, int], prices: dict[str, float]) -> float | None:
    """`None` si une position détenue n'a pas de prix : une valorisation
    partielle serait fausse sans le dire."""
    total = 0.0
    for symbol, quantity in positions.items():
        price = prices.get(symbol)
        if price is None:
            return None
        total += quantity * price
    return round(total, 2)


def signal_kind(decision_type: str | None) -> str:
    if decision_type is None:
        return "aucun"
    if decision_type in BULLISH_DECISIONS:
        return "haussier"
    if decision_type in NEUTRAL_DECISIONS:
        return "neutre"
    return "baissier"


def plan_trades(
    holdings: Holdings,
    signals: dict[str, Signal],
    prices: dict[str, float],
    risk_level: str,
    valuation_prices: dict[str, float] | None = None,
) -> list[PlannedTrade]:
    """Ordres à passer pour ce rapport (ventes puis achats). Ne modifie pas
    `holdings`.

    `prices` = prix **négociables** (clôtures récentes) : une valeur absente
    n'est jamais achetée ni vendue. `valuation_prices` (par défaut `prices`)
    sert seulement à valoriser les positions déjà détenues pour dimensionner
    les achats — il peut contenir une dernière clôture plus ancienne pour une
    valeur dont le flux de prix s'est arrêté, afin qu'une seule cotation
    manquante ne bloque pas tout le portefeuille."""
    valuation_prices = {**prices, **(valuation_prices or {})}
    planned: list[PlannedTrade] = []
    cash = holdings.cash
    positions = dict(holdings.positions)

    for symbol in sorted(positions):
        signal = signals.get(symbol)
        price = prices.get(symbol)
        if signal is None or signal_kind(signal.decision_type) != "baissier" or price is None:
            continue
        quantity = positions.pop(symbol)
        gross = quantity * price
        fees = fee_for(gross)
        cash += gross - fees
        planned.append(
            PlannedTrade(symbol, "vente", quantity, price, fees, f"Signal George devenu « {signal.decision_type} »")
        )

    current_positions_value = positions_value(positions, valuation_prices)
    if current_positions_value is None:
        # Valorisation impossible : on ne prend pas de nouveau risque à l'aveugle.
        return planned
    total_value = cash + current_positions_value
    min_cash = MIN_CASH_BY_RISK.get(risk_level, MIN_CASH_BY_RISK["indetermine"]) * total_value
    target_amount = TARGET_POSITION_WEIGHT * total_value

    candidates = sorted(
        (
            s
            for s in signals.values()
            if signal_kind(s.decision_type) == "haussier" and s.symbol not in positions and prices.get(s.symbol)
        ),
        key=lambda s: (-s.confidence, s.symbol),
    )
    for signal in candidates:
        if len(positions) >= MAX_POSITIONS:
            break
        price = prices[signal.symbol]
        budget = min(target_amount, cash - min_cash)
        quantity = math.floor(budget / (price * (1 + FEE_RATE))) if budget > 0 else 0
        if quantity < 1:
            continue
        gross = quantity * price
        fees = fee_for(gross)
        cash -= gross + fees
        positions[signal.symbol] = quantity
        planned.append(
            PlannedTrade(
                signal.symbol,
                "achat",
                quantity,
                price,
                fees,
                f"Signal George « {signal.decision_type} » (confiance {signal.confidence:.0f} %)",
            )
        )
    return planned
