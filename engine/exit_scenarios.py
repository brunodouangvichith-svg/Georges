"""Classification du scénario de sortie proposé quand une décision confirmée
franchit son take-profit ou son stop-loss — Phase 6, tâche 4.

Réutilise `engine.confidence.volume_confirmation` (même métrique que la
détection Phase 1) pour distinguer un franchissement confirmé par le volume
d'un simple bruit de clôture, comme demandé par la roadmap :

- **take-profit atteint** : toujours "sortie totale" — l'objectif de la
  figure est atteint, pas d'ambiguïté à trancher par le volume (la
  distinction volume/bruit n'est demandée par la roadmap que "dans ce
  dernier cas", c'est-à-dire pour le stop-loss).
- **stop-loss franchi, volume confirmé** (`volume_confirmation(...) >=
  VOLUME_CONFIRMED_THRESHOLD`) : "sortie totale" — la cassure invalide la
  figure de façon crédible.
- **stop-loss franchi, volume faible** : "sortie partielle" — franchissement
  ambigu (possible mèche de clôture sans conviction), on réduit l'exposition
  sans clôturer entièrement plutôt que d'ignorer complètement le signal.

Module pur (pas d'accès DB, pas d'appel LLM) — la justification textuelle
est un module séparé (`agents/explainer.py:explain_exit_scenario`, Phase 4),
qui met en mots le scénario déjà décidé ici, jamais l'inverse."""
import pandas as pd

from engine.confidence import VOLUME_LOOKBACK, volume_confirmation

VOLUME_CONFIRMED_THRESHOLD = 0.5  # volume_confirmation() >= ce seuil => franchissement confirmé (ratio >= 1.25x)


def classify_exit(
    result: str, volume: pd.Series, hit_idx: int, lookback: int = VOLUME_LOOKBACK
) -> tuple[str, bool | None]:
    """`result` : "take_profit_hit" | "stop_loss_hit" (voir
    `engine.reevaluate_decisions.evaluate_decision`). `hit_idx` : position
    entière de la séance de franchissement dans la série `volume` (même
    DataFrame que celui utilisé pour l'évaluation). Renvoie
    `(scenario, volume_confirmed)` — `volume_confirmed` est `None` pour un
    take-profit atteint (la distinction ne s'applique qu'au stop-loss)."""
    if result == "take_profit_hit":
        return "sortie_totale", None
    if result == "stop_loss_hit":
        score = volume_confirmation(volume, hit_idx, lookback=lookback)
        confirmed = score >= VOLUME_CONFIRMED_THRESHOLD
        return ("sortie_totale" if confirmed else "sortie_partielle"), confirmed
    raise ValueError(f"Résultat non géré par classify_exit : {result}")
