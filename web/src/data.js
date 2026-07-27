// L'application est branchée sur l'API réelle (voir src/api/) depuis la
// Phase 3 — ce fichier ne contient plus que ce qui n'a pas encore de
// source de données réelle dans le schéma actuel (repères macro : aucune
// table taux/indices/devises n'existe encore) et les helpers de couleur,
// partagés par toutes les vues.

export const macro = [
  { name: "Brent (USD)", value: "84.2", dir: "up" },
  { name: "EUR/USD", value: "1.072", dir: "down" },
  { name: "OAT 10 ans", value: "3.14%", dir: "up" },
  { name: "CAC 40", value: "7 940", dir: "up" },
];

export const decisionColor = (d) =>
  d === "Achat" || d === "Renforcer" ? "var(--positive)" : d === "Surveiller" ? "var(--warning)" : "var(--negative)";

export const scoreColor = (s) => (s >= 75 ? "var(--positive)" : s >= 65 ? "var(--warning)" : "var(--negative)");
