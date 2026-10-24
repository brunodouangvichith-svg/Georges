import { supabase } from "./supabaseClient";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Portail d'accès simple (Phase 9, voir CLAUDE.md section Auth) : chaque
// appel API doit porter le jeton Supabase courant. `getSession()` est
// toujours une Promise (jamais synchrone, même si elle résout depuis un
// cache en mémoire sans aller-retour réseau) — compatible avec les 3
// wrappers ci-dessous, déjà tous `async`.
async function authHeaders() {
  if (!supabase) return {};
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

// `signal` optionnel (AbortSignal) — utilisé par
// queries.js:pollPriceRefreshStatus pour arrêter le polling si l'écran qui
// l'a déclenché est démonté avant la fin (voir useRefreshPrices).
export async function apiFetch(path, params, signal) {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  const response = await fetch(url, { headers: await authHeaders(), signal });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} sur ${path}`);
  }
  return response.json();
}

export async function apiPost(path, body) {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} sur ${path}`);
  }
  return response.json();
}

export async function apiDelete(path) {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url, { method: "DELETE", headers: await authHeaders() });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} sur ${path}`);
  }
  return response.status === 204 ? null : response.json();
}

// PATCH JSON (seuils d'alerte Obligataire Watch) — les clés `undefined` du
// corps sont omises par JSON.stringify, ce qui correspond exactement à la
// sémantique "seuls les champs fournis sont modifiés" de l'API.
export async function apiPatch(path, body) {
  const url = new URL(path, API_BASE_URL);
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} sur ${path}`);
  }
  return response.json();
}
