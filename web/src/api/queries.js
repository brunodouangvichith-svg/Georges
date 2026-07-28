import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiFetch, apiPost } from "./client";

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

export function useSecurityPrices(symbol, { limit = 250 } = {}) {
  return useQuery({
    queryKey: ["security-prices", symbol, limit],
    queryFn: () => apiFetch(`/securities/${symbol}/prices`, { limit }),
    enabled: Boolean(symbol),
  });
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

// Déclenchement manuel de `python -m ingestion.ohlcv` (bouton "Mise à jour
// des prix" de la sidebar Univers) — aucune tâche planifiée n'existe encore
// (Phase 7). Invalide tout le cache : un nouveau prix affecte potentiellement
// les patterns, décisions, George Index et portefeuilles, pas juste /securities.
export function useRefreshPrices() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost("/prices/refresh"),
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
