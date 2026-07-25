// Données fictives — démonstration uniquement, ne constitue pas un conseil en investissement.

export const CAPITAL = 1_000_000;

export const positions = [
  { t: "AIR.PA", n: "Airbus", basket: "Aéronautique / Défense", weight: 8, pattern: "Breakout", conf: 85, dec: "Achat", price: 184.5, trend: [10, 12, 11, 14, 16, 15, 18, 21, 23, 26], tp: 12, sl: -7,
    explain: "Breakout confirmé par un volume en forte hausse. Carnet de commandes pluriannuel et cadences de production en accélération — c'est la conviction la plus forte du portefeuille." },
  { t: "SAF.PA", n: "Safran", basket: "Aéronautique / Défense", weight: 5, pattern: "Bull Flag", conf: 81, dec: "Achat", price: 272.3, trend: [8, 9, 9, 11, 10, 12, 13, 12, 14, 15], tp: 10, sl: -6,
    explain: "Bull Flag soutenu par la croissance des révisions de résultats sur les moteurs civils et militaires." },
  { t: "HO.PA", n: "Thales", basket: "Défense / Technologie", weight: 6, pattern: "Breakout", conf: 83, dec: "Renforcer", price: 221.8, trend: [14, 13, 15, 17, 16, 19, 21, 20, 23, 25], tp: 11, sl: -6,
    explain: "Breakout sur une ligne déjà détenue : George choisit de renforcer plutôt que d'ouvrir une nouvelle position." },
  { t: "SU.PA", n: "Schneider Electric", basket: "Industrie / Électrification", weight: 6, pattern: "Ascending Triangle", conf: 76, dec: "Achat", price: 238.9, trend: [9, 10, 10, 11, 12, 11, 13, 14, 14, 15], tp: 9, sl: -5,
    explain: "Ascending Triangle avec volumes croissants, aligné avec la thèse macro sur les data centers et réseaux électriques." },
  { t: "AI.PA", n: "Air Liquide", basket: "Industrie / Chimie", weight: 4, pattern: "Bull Flag", conf: 72, dec: "Achat", price: 167.2, trend: [11, 11, 12, 12, 13, 13, 12, 14, 14, 15], tp: 8, sl: -5,
    explain: "Bull Flag sur une valeur défensive aux marges régulières, en complément des paris plus cycliques." },
  { t: "CS.PA", n: "AXA", basket: "Assurance", weight: 4, pattern: "Bull Flag", conf: 70, dec: "Achat", price: 41.85, trend: [10, 10, 11, 10, 11, 12, 12, 13, 13, 14], tp: 8, sl: -5,
    explain: "Bull Flag associé à une discipline tarifaire soutenue du secteur de l'assurance." },
  { t: "MC.PA", n: "LVMH", basket: "Luxe (ultra haut de gamme)", weight: 2, pattern: "Double Bottom", conf: 58, dec: "Surveiller", price: 632.4, trend: [16, 15, 13, 12, 11, 12, 11, 12, 11, 12], tp: 9, sl: -5,
    explain: "Double Bottom détecté mais confiance limitée : la demande chinoise et touristique reste le facteur bloquant identifié par George." },
  { t: "BNP.PA", n: "BNP Paribas", basket: "Finance / Banque", weight: 3, pattern: "Ascending Triangle", conf: 66, dec: "Surveiller", price: 64.2, trend: [12, 12, 11, 12, 13, 12, 13, 12, 13, 13], tp: 7, sl: -5,
    explain: "Ascending Triangle, mais la sensibilité du secteur bancaire à la baisse des taux BCE limite la confiance." },
  { t: "RNO.PA", n: "Renault", basket: "Automobile", weight: 2, pattern: "Descending Triangle", conf: 45, dec: "Alléger", price: 47.6, trend: [14, 13, 13, 12, 11, 11, 10, 9, 9, 8], tp: 6, sl: -6,
    explain: "Descending Triangle — un des rares patterns baissiers détectés, cohérent avec la pression concurrentielle des VE chinois." },
  { t: "NVDA", n: "NVIDIA", basket: "IA / Semi-conducteurs", weight: 8, pattern: "Bull Flag", conf: 82, dec: "Achat", price: 128.4, trend: [9, 10, 11, 12, 13, 15, 17, 19, 21, 24], tp: 14, sl: -8,
    explain: "Bull Flag après consolidation, demande d'accélérateurs IA toujours supérieure à l'offre." },
  { t: "AMD", n: "Advanced Micro Devices", basket: "IA / Semi-conducteurs", weight: 5, pattern: "Ascending Triangle", conf: 74, dec: "Achat", price: 168.2, trend: [10, 10, 11, 12, 12, 13, 14, 14, 15, 16], tp: 11, sl: -7,
    explain: "Ascending Triangle, gains de parts de marché progressifs sur les GPU datacenter." },
  { t: "ASML", n: "ASML Holding", basket: "Semi-conducteurs", weight: 6, pattern: "Cup & Handle", conf: 78, dec: "Achat", price: 712.5, trend: [11, 10, 9, 10, 11, 13, 14, 15, 16, 18], tp: 10, sl: -6,
    explain: "Cup & Handle avec carnet de commandes EUV solide sur plusieurs années." },
  { t: "MSFT", n: "Microsoft", basket: "Technologie / IA", weight: 6, pattern: "Bull Flag", conf: 71, dec: "Achat", price: 421.3, trend: [12, 12, 13, 13, 14, 14, 15, 16, 16, 17], tp: 8, sl: -5,
    explain: "Bull Flag soutenu par la croissance du cloud Azure et des services IA." },
  { t: "GOOGL", n: "Alphabet", basket: "Technologie / IA", weight: 4, pattern: "Ascending Triangle", conf: 69, dec: "Surveiller", price: 178.9, trend: [11, 11, 12, 11, 12, 13, 12, 13, 13, 14], tp: 8, sl: -5,
    explain: "Ascending Triangle mais confiance encore limitée par la pression concurrentielle sur la recherche." },
  { t: "CRWD", n: "CrowdStrike", basket: "Cybersécurité", weight: 5, pattern: "Inverse H&S", conf: 76, dec: "Achat", price: 342.6, trend: [15, 13, 11, 12, 14, 15, 17, 18, 20, 22], tp: 12, sl: -7,
    explain: "Inverse Head & Shoulders confirmé, reprise de la confiance client après l'incident opérationnel de l'an dernier." },
  { t: "PANW", n: "Palo Alto Networks", basket: "Cybersécurité", weight: 4, pattern: "Bull Flag", conf: 70, dec: "Achat", price: 318.4, trend: [12, 12, 13, 13, 14, 14, 15, 15, 16, 17], tp: 9, sl: -6,
    explain: "Bull Flag, consolidation de la plateforme de sécurité portée par les migrations cloud." },
  { t: "NEE", n: "NextEra Energy", basket: "Énergies renouvelables", weight: 3, pattern: "Falling Wedge", conf: 65, dec: "Surveiller", price: 72.1, trend: [15, 14, 13, 12, 12, 11, 11, 10, 11, 11], tp: 7, sl: -5,
    explain: "Falling Wedge encore incomplet, sensibilité forte aux taux longs à surveiller avant renforcement." },
  { t: "NVO", n: "Novo Nordisk (ADR)", basket: "Santé", weight: 4, pattern: "Double Bottom", conf: 68, dec: "Surveiller", price: 98.7, trend: [14, 12, 11, 10, 11, 12, 11, 12, 12, 13], tp: 8, sl: -5,
    explain: "Double Bottom en formation, la dynamique des GLP-1 reste porteuse mais la concurrence s'intensifie." },
  { t: "UNH", n: "UnitedHealth Group", basket: "Santé", weight: 2, pattern: "Double Bottom", conf: 60, dec: "Surveiller", price: 512.3, trend: [16, 14, 12, 11, 12, 11, 12, 13, 12, 13], tp: 7, sl: -5,
    explain: "Double Bottom peu net, pression réglementaire persistante sur les marges." },
  { t: "SONY", n: "Sony Group (ADR)", basket: "Japon / Technologie", weight: 4, pattern: "Breakout", conf: 75, dec: "Achat", price: 89.4, trend: [11, 12, 12, 13, 14, 15, 16, 17, 18, 19], tp: 10, sl: -6,
    explain: "Breakout porté par la division jeux vidéo et capteurs d'image." },
];

export const georgeIndex = [
  { basket: "IA & Semi-conducteurs", score: 84 },
  { basket: "Aéronautique / Défense", score: 82 },
  { basket: "Cybersécurité", score: 78 },
  { basket: "Technologie / IA (mega-cap)", score: 74 },
  { basket: "Industrie / Électrification", score: 73 },
  { basket: "Japon / Technologie", score: 71 },
  { basket: "Finance / Banque", score: 66 },
  { basket: "Santé", score: 62 },
  { basket: "Luxe (ultra haut de gamme)", score: 55 },
];

export const macro = [
  { name: "Brent (USD)", value: "84.2", dir: "up" },
  { name: "EUR/USD", value: "1.072", dir: "down" },
  { name: "OAT 10 ans", value: "3.14%", dir: "up" },
  { name: "CAC 40", value: "7 940", dir: "up" },
];

export const agentEvents = [
  { name: "presse energie", desc: "Notes analystes Brent — 3 sources recoupées", time: "07:58", status: "validated" },
  { name: "macro FRED", desc: "Taux OAT 10 ans mis à jour", time: "07:59", status: "validated" },
  { name: "resultats", desc: "Calendrier T3 — 4 valeurs du panier Finance", time: "08:02", status: "validated" },
  { name: "presse sect.", desc: "Rumeur non confirmée — contrat export Airbus", time: "08:11", status: "quarantine" },
  { name: "reglementaire", desc: "Filing SEC en cours d'analyse", time: "08:24", status: "pending" },
];

export const decisionColor = (d) =>
  d === "Achat" || d === "Renforcer" ? "var(--positive)" : d === "Surveiller" ? "var(--warning)" : "var(--negative)";

export const scoreColor = (s) => (s >= 75 ? "var(--positive)" : s >= 65 ? "var(--warning)" : "var(--negative)");
