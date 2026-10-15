import { useCallback } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiFetch, apiPatch, apiPost } from "./client";

// Chaque hook correspond à un endpoint de l'API George (Phase 3, voir
// api/routers/). Pas d'endpoint de lot pour "pattern/prix par titre" côté
// API : useSecurityPatterns/useSecurityPrices sont appelés une fois par
// ligne de la watchlist (React Query dédoublonne/parallélise les requêtes,
// mais ça reste du N+1 — acceptable pour l'univers CAC 40 à ce stade, à
// revoir si l'univers suivi grossit beaucoup).

export function useSecurities({ basketId, limit = 100 } = {}) {
  return useQuery({
    queryKey: ["securities", { basketId, limit }],
    queryFn: () => apiFetch("/securities", { basket_id: basketId, limit }),
  });
}

export function useSecurityPatterns(symbol, { limit = 1 } = {}) {
  return useQuery({
    queryKey: ["security-patterns", symbol, limit],
    queryFn: () => apiFetch(`/securities/${symbol}/patterns`, { limit }),
    enabled: Boolean(symbol),
  });
}

// Dernière figure de chaque titre, pour le radar de l'écran Univers. Même
// clé de cache que useSecurityPatterns(symbol, { limit: 1 }) : les lignes
// de la watchlist lancent déjà ces requêtes, le radar les réutilise sans
// appel supplémentaire. Renvoie { [symbol]: pattern | null }.
export function useLatestPatterns(symbols) {
  // combine stable tant que la liste de titres ne change pas : React Query
  // ne recalcule alors le dictionnaire que quand une requête évolue.
  const combine = useCallback(
    (results) => Object.fromEntries(symbols.map((symbol, i) => [symbol, results[i]?.data?.items?.[0] ?? null])),
    [symbols]
  );
  return useQueries({
    queries: symbols.map((symbol) => ({
      queryKey: ["security-patterns", symbol, 1],
      queryFn: () => apiFetch(`/securities/${symbol}/patterns`, { limit: 1 }),
      enabled: Boolean(symbol),
    })),
    combine,
  });
}

export function useSecurityPrices(symbol, { limit = 250 } = {}) {
  return useQuery({
    queryKey: ["security-prices", symbol, limit],
    queryFn: () => apiFetch(`/securities/${symbol}/prices`, { limit }),
    enabled: Boolean(symbol),
  });
}

export function useSecurityFundamentals(symbol) {
  return useQuery({
    queryKey: ["security-fundamentals", symbol],
    queryFn: () => apiFetch(`/securities/${symbol}/fundamentals`),
    enabled: Boolean(symbol),
    retry: false, // 404 attendu tant que l'import quotidien n'a jamais tourné pour ce titre
  });
}

export function useSecurityDividends(symbol, { limit = 5 } = {}) {
  return useQuery({
    queryKey: ["security-dividends", symbol, limit],
    queryFn: () => apiFetch(`/securities/${symbol}/dividends`, { limit }),
    enabled: Boolean(symbol),
  });
}

export function useEnergyPrices() {
  return useQuery({ queryKey: ["energy-prices"], queryFn: () => apiFetch("/energy-prices") });
}

export function useBaskets() {
  return useQuery({ queryKey: ["baskets"], queryFn: () => apiFetch("/baskets") });
}

export function useGeorgeIndex(basketId) {
  return useQuery({
    queryKey: ["george-index", basketId],
    queryFn: () => apiFetch(`/baskets/${basketId}/george-index`),
    enabled: basketId != null,
  });
}

export function useDecisions({ decisionType, status, basketId, limit = 100 } = {}) {
  return useQuery({
    queryKey: ["decisions", { decisionType, status, basketId, limit }],
    queryFn: () =>
      apiFetch("/decisions", { decision_type: decisionType, status, basket_id: basketId, limit }),
  });
}

export function useAgentActivity({ status, limit = 20 } = {}) {
  return useQuery({
    queryKey: ["agent-activity", { status, limit }],
    queryFn: () => apiFetch("/agents/activity", { status, limit }),
  });
}

// Couche LLM (Phase 4) — mutations, pas des useQuery : chaque appel déclenche
// un vrai appel Mistral côté serveur (coût/latence), on ne veut donc jamais
// les déclencher automatiquement au montage ou au changement de sélection,
// seulement sur une action explicite de l'utilisateur.
export function useChat() {
  return useMutation({
    mutationFn: (question) => apiPost("/chat", { question }),
  });
}

export function useExplainDecision() {
  return useMutation({
    mutationFn: ({ decisionId, includeSecondOpinion = false }) =>
      apiPost(`/decisions/${decisionId}/explanation`, { include_second_opinion: includeSecondOpinion }),
  });
}

// Portefeuilles nommés (écran Mon Portefeuille) — persistés côté base
// (api/routers/portfolios.py), pas en localStorage : ils doivent survivre
// au navigateur qui les a créés.
export function usePortfolios() {
  return useQuery({ queryKey: ["portfolios"], queryFn: () => apiFetch("/portfolios") });
}

export function useCreatePortfolio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, decisionIds }) => apiPost("/portfolios", { name, decision_ids: decisionIds }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portfolios"] }),
  });
}

export function useDeletePortfolio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (portfolioId) => apiDelete(`/portfolios/${portfolioId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portfolios"] }),
  });
}

export function useRemoveDecisionFromPortfolio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ portfolioId, decisionId }) => apiDelete(`/portfolios/${portfolioId}/decisions/${decisionId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portfolios"] }),
  });
}

// Répartition d'un budget entre les décisions d'un portefeuille (action
// vocale "Demander à George") — calcul déterministe côté serveur
// (engine/portfolio_allocation.py), pas un appel LLM.
export function useAllocateBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ portfolioId, budget }) => apiPost(`/portfolios/${portfolioId}/allocate`, { budget }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portfolios"] }),
  });
}

// Déclenchement manuel de `python -m ingestion.price_history` (bouton "Mise
// à jour des prix" de la sidebar Univers) — aucune tâche planifiée à
// fréquence fine n'existe encore (Phase 7). L'endpoint est asynchrone côté
// serveur (voir api/routers/prices.py) : `POST /prices/refresh` répond
// immédiatement avec un statut "running", le job (10 ans d'historique par
// titre sur tout l'univers) tourne en tâche de fond, et ce hook fait le
// polling sur `GET /prices/refresh` jusqu'à "done"/"failed" avant de
// résoudre — remplace un ancien design synchrone dont le timeout mobile fixe
// (2 min) finissait par être dépassé une fois le backend passé à 10 ans.
// Invalide tout le cache une fois terminé : un nouveau prix affecte
// potentiellement les patterns, décisions, George Index et portefeuilles,
// pas juste /securities.
//
// Trois garde-fous ajoutés après revue (`_state` du backend est en mémoire
// seule, sans persistance — voir `api/routers/prices.py` — et ne survit
// donc pas à un redémarrage du service Render pendant un job) :
// - `PRICE_REFRESH_MAX_WAIT_MS` borne la durée totale du polling : sans ça,
//   un redémarrage serveur en plein job réinitialise silencieusement l'état
//   à "idle", que cette boucle prendrait pour "toujours en cours" et
//   attendrait indéfiniment — pire que l'ancien timeout fixe qui, lui,
//   finissait toujours par afficher une erreur.
// - `PRICE_REFRESH_MAX_CONSECUTIVE_ERRORS` tolère quelques échecs réseau
//   transitoires sur un seul appel sans faire échouer tout le
//   rafraîchissement — le polling multiplie les fenêtres de risque réseau
//   par rapport à l'ancien appel bloquant unique.
// - `signal` (AbortSignal, optionnel) permet d'arrêter le polling si
//   l'écran qui l'a déclenché (Univers.jsx) est démonté avant la fin, pour
//   ne pas continuer à interroger le serveur ni invalider le cache pour un
//   écran qui n'est plus affiché.
const PRICE_REFRESH_POLL_INTERVAL_MS = 3000;
const PRICE_REFRESH_MAX_WAIT_MS = 10 * 60 * 1000;
const PRICE_REFRESH_MAX_CONSECUTIVE_ERRORS = 3;

async function pollPriceRefreshStatus(signal) {
  const deadline = Date.now() + PRICE_REFRESH_MAX_WAIT_MS;
  let consecutiveErrors = 0;
  while (true) {
    if (signal?.aborted) {
      throw new DOMException("Rafraîchissement annulé (écran fermé)", "AbortError");
    }
    if (Date.now() > deadline) {
      throw new Error(
        `Le rafraîchissement des prix prend plus de ${PRICE_REFRESH_MAX_WAIT_MS / 60000} minutes — réessayez plus tard.`,
      );
    }

    let status;
    try {
      status = await apiFetch("/prices/refresh", undefined, signal);
      consecutiveErrors = 0;
    } catch (err) {
      if (signal?.aborted) throw err;
      consecutiveErrors += 1;
      if (consecutiveErrors > PRICE_REFRESH_MAX_CONSECUTIVE_ERRORS) throw err;
      await new Promise((resolve) => setTimeout(resolve, PRICE_REFRESH_POLL_INTERVAL_MS));
      continue;
    }

    if (status.status === "done" || status.status === "failed") return status;
    await new Promise((resolve) => setTimeout(resolve, PRICE_REFRESH_POLL_INTERVAL_MS));
  }
}

export function useRefreshPrices() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (signal) => {
      await apiPost("/prices/refresh");
      const status = await pollPriceRefreshStatus(signal);
      if (status.status === "failed") {
        throw new Error(status.error ?? "Échec du rafraîchissement des prix.");
      }
      return status;
    },
    onSuccess: () => queryClient.invalidateQueries(),
  });
}

// Déclenchement manuel d'une tâche de collecte (Phase 7, MVP) — voir
// api/routers/agents.py:trigger_collection. Pas de scheduler encore : c'est
// le seul moyen de peupler /agents/activity avec de vraies données pour
// l'instant.
export function useTriggerCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (taskType) => apiPost("/agents/collect", { task_type: taskType }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["agent-activity"] }),
  });
}

// Obligataire Watch (onglet "Obligataire", voir api/routers/bonds.py). Toutes
// les clés commencent par "bonds" : une mise à jour (collecte ou seuil)
// invalide tout l'onglet d'un coup.
export function useBondDashboard() {
  return useQuery({ queryKey: ["bonds", "dashboard"], queryFn: () => apiFetch("/bonds") });
}

export function useBondHistory(instrument, { limit = 2000 } = {}) {
  return useQuery({
    queryKey: ["bonds", "history", instrument, limit],
    queryFn: () => apiFetch(`/bonds/${instrument}/history`, { limit }),
    enabled: Boolean(instrument),
  });
}

export function useBondThresholds() {
  return useQuery({ queryKey: ["bonds", "thresholds"], queryFn: () => apiFetch("/bonds/alerts/thresholds") });
}

export function useBondAlertEvents({ status, limit = 50 } = {}) {
  return useQuery({
    queryKey: ["bonds", "events", { status, limit }],
    queryFn: () => apiFetch("/bonds/alerts/events", { status, limit }),
  });
}

export function useBondCollectionRuns({ limit = 10 } = {}) {
  return useQuery({
    queryKey: ["bonds", "runs", limit],
    queryFn: () => apiFetch("/bonds/collection-runs", { limit }),
  });
}

export function useBondBulletin() {
  return useQuery({ queryKey: ["bonds", "bulletin"], queryFn: () => apiFetch("/bonds/bulletin") });
}

export function useUpdateBondThreshold() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, thresholdPct, enabled }) =>
      apiPatch(`/bonds/alerts/thresholds/${id}`, { threshold_pct: thresholdPct, enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bonds"] }),
  });
}

// Collecte manuelle (4 appels FRED côté serveur, synchrone et rapide —
// contrairement à useRefreshPrices, pas de polling nécessaire).
export function useRefreshBonds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost("/bonds/refresh"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bonds"] }),
  });
}
