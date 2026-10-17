// Géométrie du radar de l'écran Univers (voir UniversRadar.jsx) — séparée
// du composant pour pouvoir être testée seule et garder le fast refresh.

export const CX = 380;
export const CY = 340;
// Échelle radiale de tout le radar (disque, graduations, barres, étiquettes,
// tracé de l'historique) : 0.9 = disque réduit de 10 % par rapport au dessin
// d'origine (rayon 250), à la demande de l'utilisateur. Le viewBox ne change
// pas, le radar garde donc la même place à l'écran avec plus de marge.
export const RADAR_SCALE = 0.9;
export const R_IN = 250 * RADAR_SCALE;
export const R_TICK_IN = 256 * RADAR_SCALE;
export const R_TICK_OUT = 264 * RADAR_SCALE;
export const R_BAR = 270 * RADAR_SCALE;
export const BAR_SCALE = 0.5 * RADAR_SCALE;
const R_SECTOR_LABEL = 236 * RADAR_SCALE;
const SECTOR_GAP = 2;
const MIN_SECTOR_LABEL = 3;
const MAX_LABEL_CHARS = 24;

// Ramène un angle en degrés dans [-180, 180[.
const normalizeDeg = (d) => ((((d + 180) % 360) + 360) % 360) - 180;

const truncate = (s, n) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// Le radar regroupe par grande famille de secteur (la partie avant " / " :
// "Santé / Biotechnologie" et "Santé / Pharmacie" → "Santé"), sinon les ~70
// sous-secteurs de l'univers ne comptent presque tous qu'1 à 3 valeurs et
// seuls 2 d'entre eux recevaient une étiquette. Les familles de moins de
// MIN_FAMILY_SIZE valeurs sont réunies dans "Autres secteurs", placé en
// dernier. La watchlist garde le secteur complet.
export const OTHER_FAMILY = "Autres secteurs";
const MIN_FAMILY_SIZE = 3;

export function sectorFamily(sector) {
  return (sector || "Autre").split(" / ")[0].trim() || "Autre";
}

export function buildRadar(securities, patternsBySymbol, decisionsMap) {
  const families = new Map();
  for (const s of securities) {
    const key = sectorFamily(s.sector);
    if (!families.has(key)) families.set(key, []);
    families.get(key).push(s);
  }
  const groups = new Map();
  const others = [];
  for (const [family, list] of families) {
    if (list.length >= MIN_FAMILY_SIZE) groups.set(family, list);
    else others.push(...list);
  }
  const sectors = [...groups.entries()].sort((a, b) => b[1].length - a[1].length);
  if (others.length) sectors.push([OTHER_FAMILY, others]);
  const slots = securities.length + sectors.length * SECTOR_GAP;
  const step = slots > 0 ? (Math.PI * 2) / slots : 0;

  const items = [];
  const labels = [];
  let slot = 0;
  for (const [sector, list] of sectors) {
    const start = slot;
    for (const s of list) {
      const angle = -Math.PI / 2 + slot * step;
      const pattern = patternsBySymbol?.[s.symbol] ?? null;
      const decision = decisionsMap?.[s.symbol]?.decision_type ?? null;
      items.push({
        symbol: s.symbol,
        name: s.name,
        angle,
        confidence: pattern ? Math.max(0, Math.min(100, pattern.confidence)) : null,
        decision,
        lighten: decision != null && decision !== "Achat" && decision !== "Renforcer" && decision !== "Surveiller",
      });
      slot++;
    }
    if (list.length >= MIN_SECTOR_LABEL) {
      // Étiquette orientée selon le rayon (de l'anneau vers le centre) et non
      // horizontale : deux secteurs voisins sont séparés d'au moins ~10° et
      // une étiquette n'occupe que ~3° (hauteur de police / rayon), elles ne
      // peuvent donc plus se chevaucher, même en haut et en bas du cercle où
      // les étiquettes horizontales se recouvraient. Moitié gauche retournée
      // de 180° pour que le texte reste lisible (jamais à l'envers).
      const mid = -Math.PI / 2 + (start + (list.length - 1) / 2) * step;
      const right = Math.cos(mid) >= 0;
      const deg = (mid * 180) / Math.PI;
      labels.push({
        sector,
        text: truncate(sector.toUpperCase(), MAX_LABEL_CHARS),
        x: CX + Math.cos(mid) * R_SECTOR_LABEL,
        y: CY + Math.sin(mid) * R_SECTOR_LABEL,
        rotate: normalizeDeg(right ? deg : deg + 180),
        anchor: right ? "end" : "start",
      });
    }
    slot += SECTOR_GAP;
  }
  return { items, labels };
}

