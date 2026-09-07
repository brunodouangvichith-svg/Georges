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

**Repli DeepSeek (ajouté après un incident réel de rate limit Mistral en
production, sept. 2026)** : `complete()`/`complete_vision()` restent
d'abord des appels Mistral — DeepSeek n'est sollicité que si Mistral échoue
après ses propres `max_retries` (clé manquante, quota épuisé, service
injoignable). Un seul essai côté DeepSeek, sans retry propre, pour borner la
latence totale d'un appel déjà en échec. Si `DEEPSEEK_API_KEY` n'est pas
configurée, le repli est silencieusement ignoré et l'erreur Mistral d'origine
remonte inchangée — comportement identique à avant cet ajout pour tout
environnement qui n'a pas cette variable (dev local, tests). `embed()` reste
exclusivement sur Mistral : DeepSeek n'expose pas d'endpoint d'embeddings.
"""
import os
import time

import httpx
from mistralai.client import Mistral

MODEL_SMALL = "mistral-small-latest"  # George : explication, /chat, rapports
MODEL_LARGE = "mistral-large-latest"  # Jane : veille méthodologique, second avis
EMBED_MODEL = "mistral-embed"

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
# Correspondance modèle Mistral -> modèle DeepSeek de repli, même logique
# "petit/gros modèle" que MODEL_SMALL/MODEL_LARGE. `deepseek-reasoner` pour
# le gros modèle : c'est `deepseek-chat` avec le raisonnement en chaîne
# activé (vérifié en direct), plus proche du rôle "second avis" de Jane que
# la simple explication de George.
DEEPSEEK_TEXT_MODEL_MAP = {
    MODEL_SMALL: "deepseek-chat",
    MODEL_LARGE: "deepseek-reasoner",
}
# Modèle vision dédié, distinct des modèles texte (confirmé en direct) —
# encore expérimental côté DeepSeek au moment de cet ajout.
DEEPSEEK_VISION_MODEL = "deepseek-v4-flash-vision-exp"

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


def _complete_with_deepseek_fallback(messages: list[dict], deepseek_model: str, temperature: float, mistral_err: Exception) -> str:
    """Dernier recours après l'échec de Mistral (voir docstring du module).
    Un seul essai — pas de retry propre ici, la latence a déjà été dépensée
    côté Mistral. Ré-émet `mistral_err` tel quel (pas d'appel réseau) si
    `DEEPSEEK_API_KEY` n'est pas configurée, pour ne rien changer au
    comportement des environnements qui n'ont pas cette variable."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise mistral_err
    try:
        response = httpx.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": deepseek_model, "messages": messages, "temperature": temperature},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as deepseek_err:  # noqa: BLE001 — échec réseau/API/parsing, tous traités pareil
        raise MistralUnavailableError(
            f"Mistral indisponible ({mistral_err}) et repli DeepSeek également en échec : {deepseek_err}"
        ) from deepseek_err


def complete(
    system_prompt: str,
    user_message: str,
    model: str = MODEL_SMALL,
    temperature: float = 0.3,
    max_retries: int = 3,
    allow_fallback: bool = True,
) -> str:
    """Appel isolé pour faciliter une future migration vers un autre
    fournisseur (ex. Claude en production, voir `George_Stack_Technique.pdf`)
    — sert aujourd'hui de point d'entrée unique pour le repli DeepSeek.
    `allow_fallback=False` désactive ce repli et laisse `MistralUnavailableError`
    remonter immédiatement — nécessaire pour les appelants dont le contrat est
    justement de dégrader vite plutôt que d'attendre un second fournisseur
    (voir `agents/jane.py:reformulate_formal` et
    `agents/email_formatter.py:format_email_body`, dont la docstring dit
    explicitement qu'un échec de mise en forme ne doit jamais bloquer)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    try:
        return _complete_with_messages(messages, model, temperature, max_retries)
    except MistralUnavailableError as mistral_err:
        if not allow_fallback:
            raise
        deepseek_model = DEEPSEEK_TEXT_MODEL_MAP.get(model, "deepseek-chat")
        return _complete_with_deepseek_fallback(messages, deepseek_model, temperature, mistral_err)


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
    try:
        return _complete_with_messages(messages, model, temperature, max_retries)
    except MistralUnavailableError as mistral_err:
        # Forme de `image_url` différente de celle de Mistral ci-dessus
        # (objet `{"url": ...}`, pas une chaîne nue) — vérifié en direct
        # contre l'API DeepSeek, dérivé des messages plutôt que réutilisé
        # tel quel.
        deepseek_content = [{"type": "text", "text": user_text}] + [
            {"type": "image_url", "image_url": {"url": uri}} for uri in image_data_uris
        ]
        deepseek_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": deepseek_content},
        ]
        return _complete_with_deepseek_fallback(deepseek_messages, DEEPSEEK_VISION_MODEL, temperature, mistral_err)


def embed(texts: list[str], model: str = EMBED_MODEL) -> list[list[float]]:
    """Vecteurs d'embedding pour l'indexation pgvector des rapports/notes
    (tâche 4 de la Phase 4)."""
    client = _get_client()
    response = client.embeddings.create(model=model, inputs=texts)
    return [row.embedding for row in response.data]
