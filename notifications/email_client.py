"""Client Resend (envoi d'email réel, ad hoc — pas une phase du roadmap),
demandé directement par l'utilisateur pour le partage par email d'une
explication de George (texte + graphique 10 ans en pièce jointe).

Suit exactement le même contrat que `agents/mistral_client.py`/`api/auth.py` :
`RESEND_API_KEY` lu au moment de l'appel, jamais à l'import — importer ce
module reste possible (et testable) sans clé configurée. Un vrai appel HTTP
via `httpx` (déjà une dépendance du projet), pas le SDK officiel `resend` :
l'API REST de Resend est un simple POST JSON, pas besoin d'une dépendance
supplémentaire pour ça.

**Limite de compte connue, documentée pour l'utilisateur** : sans domaine
vérifié sur Resend, l'adresse `from` par défaut (`onboarding@resend.dev`,
le bac à sable fourni par Resend) ne peut envoyer qu'à l'adresse email du
compte Resend lui-même — un envoi vers une autre adresse échoue avec un vrai
403 de l'API Resend tant qu'aucun domaine n'est vérifié. Ce n'est pas un bug
de ce client, c'est une restriction du compte ; `EmailUnavailableError`
remonte le message d'erreur réel de Resend tel quel plutôt que de le
masquer, pour que ce cas soit diagnosticable depuis les logs."""
import base64
import os

import httpx

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM_ADDRESS = "George <onboarding@resend.dev>"


class EmailUnavailableError(RuntimeError):
    """Clé API manquante ou service Resend injoignable/en erreur — classe
    dédiée (pas `RuntimeError` nu), même raison que `MistralUnavailableError`/
    `SupabaseUnavailableError` : un handler FastAPI enregistré sur cette
    sous-classe reste sous `CORSMiddleware` (voir CLAUDE.md, section Phase 3,
    pour le piège Starlette déjà documenté avec `Exception` nu)."""


def send_email(
    to_email: str,
    subject: str,
    text: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise EmailUnavailableError("Variable d'environnement RESEND_API_KEY manquante.")

    payload = {
        "from": DEFAULT_FROM_ADDRESS,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }
    if attachment_bytes is not None:
        payload["attachments"] = [
            {
                "filename": attachment_filename or "graphique.png",
                "content": base64.b64encode(attachment_bytes).decode("ascii"),
            }
        ]

    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise EmailUnavailableError(f"Service Resend injoignable : {exc}") from exc

    if response.status_code >= 400:
        raise EmailUnavailableError(f"Resend a refusé l'envoi ({response.status_code}) : {response.text}")
