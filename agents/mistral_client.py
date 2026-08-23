"""Client Mistral partagé par tous les sous-agents LLM de George (Phase 4) —
généralise `mistral_client.py` (racine du repo, fourni comme pattern de
référence par la roadmap) en un module unique réutilisé par l'explainer,
Jane et la génération de rapports, plutôt que de dupliquer la logique
d'appel/retry dans chacun.

Le client est instancié à la première utilisation (`_get_client`), pas à
l'import du module : `MISTRAL_API_KEY` n'est nécessaire qu'au moment d'un
appel réel, ce qui permet d'importer `agents.*` (et donc de les tester) sans
clé configurée — même principe que `ingestion/db.py:get_database_url()`
résolue à l'appel plutôt qu'à l'import.
"""
import os
import time

from mistralai.client import Mistral

MODEL_SMALL = "mistral-small-latest"  # George : explication, /chat, rapports
MODEL_LARGE = "mistral-large-latest"  # Jane : veille méthodologique, second avis
EMBED_MODEL = "mistral-embed"

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

class MistralUnavailableError(RuntimeError):
    """Clé API manquante, quota épuisé après retries, ou API injoignable —
    classe dédiée (plutôt que `RuntimeError` nu) pour permettre à `api/main.py`
    de lui enregistrer un handler FastAPI spécifique qui reste sous
    `CORSMiddleware`, sur le même principe que `SQLAlchemyError` (voir
    CLAUDE.md, section Phase 3, pour le piège Starlette évité)."""


_client: Mistral | None = None


def _get_client() -> Mistral:
    global _client
    if _client is None:
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise MistralUnavailableError("Variable d'environnement MISTRAL_API_KEY manquante.")
        _client = Mistral(api_key=api_key)
    return _client


def load_system_prompt(name: str) -> str:
    """Charge un prompt système depuis un fichier texte de `agents/prompts/`
    (contrainte Phase 4 : jamais de prompt en dur dans le code Python, pour
    pouvoir les faire évoluer sans redéployer)."""
    path = os.path.join(PROMPTS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _complete_with_messages(messages: list[dict], model: str, temperature: float, max_retries: int) -> str:
    """Backoff exponentiel simple sur le rate limit du tier gratuit, partagé
    par `complete()` et `complete_vision()` — la seule différence entre les
    deux est la forme du message utilisateur (texte brut vs. liste de
    chunks texte+image)."""
    client = _get_client()
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.chat.complete(model=model, messages=messages, temperature=temperature)
            return response.choices[0].message.content
        except Exception as err:  # noqa: BLE001 — tout échec réseau/API déclenche un retry
            last_err = err
            time.sleep(2**attempt)
    raise MistralUnavailableError(f"Échec de l'appel Mistral après {max_retries} tentatives : {last_err}")


def complete(system_prompt: str, user_message: str, model: str = MODEL_SMALL, temperature: float = 0.3, max_retries: int = 3) -> str:
    """Appel isolé pour faciliter une future migration vers un autre
    fournisseur (ex. Claude en production, voir `George_Stack_Technique.pdf`)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    return _complete_with_messages(messages, model, temperature, max_retries)


def complete_vision(
    system_prompt: str,
    user_text: str,
    image_data_uris: list[str],
    model: str = MODEL_SMALL,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> str:
    """Comme `complete()`, mais pour un message utilisateur multimodal
    (texte + une ou plusieurs images) — utilisé par `agents/jane_veille.py`
    pour décrire un diagramme d'analyse technique. `mistral-small-latest`
    (`MODEL_SMALL`, par défaut ici) supporte la vision nativement depuis
    Mistral Small 3.1 (mars 2025) : pas besoin d'un modèle dédié séparé, ni
    de `MODEL_LARGE` (dont le support vision n'est pas confirmé — voir
    `agents/jane_veille.py`, qui documente ce choix explicitement).
    `image_data_uris` : chaînes `data:image/...;base64,...` déjà encodées
    (voir `agents/jane_veille.py:_encode_image_data_uri`)."""
    content = [{"type": "text", "text": user_text}] + [
        {"type": "image_url", "image_url": uri} for uri in image_data_uris
    ]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]
    return _complete_with_messages(messages, model, temperature, max_retries)


def embed(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Vecteurs d'embedding pour l'indexation pgvector des rapports/notes
    (tâche 4 de la Phase 4)."""
    client = _get_client()
    response = client.embeddings.create(model=model, inputs=texts)
    return [row.embedding for row in response.data]
