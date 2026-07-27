"""Répartition d'un budget entre les décisions d'un portefeuille nommé
(écran « Mon Portefeuille », action « Demander à George » — voir
`api/routers/portfolios.py:allocate_portfolio_budget`).

Module pur (pas d'accès DB, pas d'appel LLM) — même principe que
`engine/exit_levels.py` : une allocation budgétaire précise est un calcul,
pas quelque chose à laisser décider à un modèle de langage (voir
`agents/chat.py`, où un modèle "small" s'est montré peu fiable pour
énumérer/calculer sur plusieurs dizaines d'entrées structurées).

Formule : chaque décision reçoit un poids = confiance (0-1) × ratio
gain/risque (amplitude du take-profit / amplitude du stop-loss, par rapport
au prix d'entrée) — une décision plus crédible et mieux rémunérée pour son
risque reçoit une part plus grande du budget. Le budget est réparti
proportionnellement aux poids, puis converti en un nombre entier d'actions
(troncature : impossible d'acheter une fraction d'action sur ces marchés)."""
from __future__ import annotations

MIN_WEIGHT = 0.01  # évite un poids nul (ex. take-profit ou stop-loss manquant) qui exclurait totalement une ligne


def _weight(entry_price: float, stop_loss: float | None, take_profit: float | None, confidence: float) -> float:
    risk = abs(entry_price - stop_loss) / entry_price if stop_loss else None
    reward = abs(take_profit - entry_price) / entry_price if take_profit else None
    ratio = reward / risk if risk and reward and risk > 0 else 1.0
    return max((confidence / 100) * ratio, MIN_WEIGHT)


def allocate_budget(decisions: list[dict], budget: float) -> list[dict]:
    """`decisions` : liste de dicts avec au moins `decision_id`, `entry_price`,
    `confidence`, et optionnellement `stop_loss`/`take_profit`. Renvoie une
    liste alignée de `{"decision_id", "quantity", "amount"}` — `quantity` en
    nombre entier d'actions, `amount` le montant réellement engagé
    (`quantity × entry_price`, toujours ≤ la part théorique et jamais négatif).
    Liste vide ou budget ≤ 0 renvoie une liste vide plutôt que de diviser par
    zéro."""
    if not decisions or budget <= 0:
        return []

    weights = [
        _weight(d["entry_price"], d.get("stop_loss"), d.get("take_profit"), d["confidence"]) for d in decisions
    ]
    total_weight = sum(weights)

    allocations = []
    for d, weight in zip(decisions, weights):
        share = budget * weight / total_weight
        quantity = int(share // d["entry_price"])
        allocations.append(
            {"decision_id": d["decision_id"], "quantity": quantity, "amount": round(quantity * d["entry_price"], 2)}
        )
    return allocations


def format_allocation_summary(decisions: list[dict], allocations: list[dict], budget: float) -> str:
    """Texte déterministe résumant une répartition — pas d'appel LLM, même
    raisonnement que `agents/chat.py:_format_opportunities` : restituer
    fidèlement un calcul déjà fait ne demande aucune capacité de langage
    naturel, seulement de ne rien perdre en chemin. `decisions` doit ici
    inclure `symbol` (en plus des champs lus par `allocate_budget`)."""
    by_id = {d["decision_id"]: d for d in decisions}
    lines = []
    total_engaged = 0.0
    for alloc in allocations:
        d = by_id[alloc["decision_id"]]
        lines.append(f"- {d['symbol']} : {alloc['quantity']} actions × {d['entry_price']:.2f} € = {alloc['amount']:.2f} €")
        total_engaged += alloc["amount"]
    remainder = budget - total_engaged
    header = f"Répartition d'un budget de {budget:,.2f} € sur {len(allocations)} ligne(s) (pondération confiance × ratio gain/risque) :"
    footer = f"Total engagé : {total_engaged:,.2f} € — reste non alloué (arrondi aux actions entières) : {remainder:,.2f} €."
    return "\n".join([header, *lines, footer])
