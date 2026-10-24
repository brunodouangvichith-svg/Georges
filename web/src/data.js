// L'application est branchée sur l'API réelle (voir src/api/) depuis la
// Phase 3 — ce fichier ne contient plus que les helpers de couleur,
// partagés par toutes les vues (le dernier repère fictif, "Repères macro",
// a été remplacé par la tuile "Marché d'énergie", branchée sur
// GET /energy-prices — voir Univers.jsx).

export const decisionColor = (d) =>
  d === "Achat" || d === "Renforcer" ? "var(--positive)" : d === "Surveiller" ? "var(--warning)" : "var(--negative)";

// Classes CSS du tag de décision (index.css) — mêmes couleurs que
// decisionColor : vert achat/renfort, orange surveiller, rouge sinon.
export const decisionTagClass = (d) =>
  d === "Achat" || d === "Renforcer"
    ? "gd-tag gd-tag-achat"
    : d === "Surveiller"
      ? "gd-tag gd-tag-surveiller"
      : "gd-tag gd-tag-alleger";

export const scoreColor = (s) => (s >= 75 ? "var(--positive)" : s >= 65 ? "var(--warning)" : "var(--negative)");
