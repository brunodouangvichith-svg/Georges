import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "george.portfolio.decisionIds";

function readStoredIds() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

// Sélection "Mon Portefeuille" purement côté client (localStorage) : aucun
// système de comptes/authentification n'existe encore (voir CLAUDE.md,
// Phase 9), donc pas de notion de portefeuille par utilisateur persistable
// côté serveur à ce stade — cocher une décision dans Paniers ne survit que
// dans ce navigateur, pas entre appareils.
export function usePortfolioSelection() {
  const [ids, setIds] = useState(readStoredIds);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  }, [ids]);

  const isSelected = useCallback((id) => ids.has(id), [ids]);

  const toggle = useCallback((id) => {
    setIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return { ids, isSelected, toggle };
}
