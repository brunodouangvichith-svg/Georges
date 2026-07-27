"""
Client Mistral pour la couche LLM conversationnelle de George.

Prérequis :
    pip install mistralai --break-system-packages
    export MISTRAL_API_KEY="ta_cle_ici"   (jamais en dur dans le code)
"""
import os
import time
from mistralai import Mistral

API_KEY = os.environ.get("MISTRAL_API_KEY")
if not API_KEY:
    raise RuntimeError("Variable d'environnement MISTRAL_API_KEY manquante.")

client = Mistral(api_key=API_KEY)

# Modèles courants (vérifier les noms exacts disponibles sur docs.mistral.ai
# au moment de l'implémentation, ils évoluent) :
#   - mistral-large-latest   : le plus capable, quota gratuit plus restreint
#   - mistral-small-latest   : bon compromis coût/qualité
#   - open-mistral-nemo      : modèle ouvert, alternative auto-hébergeable
MODEL = "mistral-small-latest"


def load_system_prompt(path: str) -> str:
    """Le prompt système vit dans un fichier texte séparé (voir contrainte
    Phase 4), pas en dur dans le code Python."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def explain_decision(system_prompt: str, decision_context: dict, max_retries: int = 3) -> str:
    """
    Appelle Mistral pour générer l'explication d'une décision de George.
    decision_context : dict structuré (pattern, confiance, ticker, etc.)
    — jamais de texte libre non structuré envoyé au modèle pour cette tâche,
    pour respecter le principe : le LLM met en mots, il ne détecte rien.
    """
    user_message = (
        f"Voici les données de la décision à expliquer (ne rien inventer, "
        f"n'utiliser que ces chiffres) :\n{decision_context}"
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.complete(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,  # peu de créativité souhaitée pour du factuel
            )
            return response.choices[0].message.content

        except Exception as err:
            # Le tier gratuit impose un rate limit : backoff exponentiel simple
            wait = 2 ** attempt
            print(f"Erreur API ({err}), nouvelle tentative dans {wait}s...")
            time.sleep(wait)

    raise RuntimeError("Échec après plusieurs tentatives — vérifier le quota API.")


if __name__ == "__main__":
    system_prompt = load_system_prompt("prompts/explainer_system.txt")

    decision_context = {
        "ticker": "AIR.PA",
        "pattern": "Breakout",
        "confidence": 85,
        "decision": "Achat",
        "take_profit_pct": 12,
        "stop_loss_pct": -7,
    }

    explanation = explain_decision(system_prompt, decision_context)
    print(explanation)
