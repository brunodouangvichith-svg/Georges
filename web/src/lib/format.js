// Formats d'affichage français partagés (onglets "Rapport" et "Trading").
export const nf = (value, digits = 2) =>
  value == null ? "—" : Number(value).toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const eur = (value) => (value == null ? "—" : `${nf(value)} €`);
export const signed = (value, unit = " %", digits = 2) => (value == null ? "—" : `${value > 0 ? "+" : ""}${nf(value, digits)}${unit}`);
// Une date seule ("2026-10-23") est lue comme minuit UTC : la formater en UTC
// évite d'afficher la veille à l'ouest d'UTC. Un horodatage reste en heure locale.
export const dateFr = (iso) =>
  iso
    ? new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric", timeZone: /^\d{4}-\d{2}-\d{2}$/.test(iso) ? "UTC" : undefined })
    : "—";
