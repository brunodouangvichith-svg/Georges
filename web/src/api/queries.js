import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch, apiPost } from "./client";

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
