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

// Écart entre deux angles en radians, dans [0, π].
const angleGap = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));

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

// Radar étroit (téléphone) : sous cette largeur affichée, les libellés de
// secteur à taille fixe tomberaient vers 4 px.
export const COMPACT_BELOW = 500;
const COMPACT_LABEL_PX = 11;
export const LABEL_SIZE = 10.5;
// Longueur radiale maximale d'un libellé agrandi (unités du viewBox) : il
// reste hors du centre du disque.
const COMPACT_LABEL_LENGTH = 130;
const MONO_RATIO = 0.62; // largeur d'un caractère / taille de police
const TAP_PX = 22; // tolérance autour de l'anneau (demi-cible de 44 px)

// Libellés pour un radar affiché à `scale` px par unité (zoom compris) :
// police agrandie pour mesurer ~11 px à l'écran, textes raccourcis, et
// secteurs masqués quand ils chevaucheraient un secteur plus gros déjà gardé
// (`labels` est trié du plus gros au plus petit).
export function compactLabels(labels, scale) {
  const fontSize = Math.max(LABEL_SIZE, COMPACT_LABEL_PX / scale);
  const maxChars = Math.max(6, Math.min(MAX_LABEL_CHARS, Math.floor(COMPACT_LABEL_LENGTH / (fontSize * MONO_RATIO))));
  const kept = [];
  for (const label of labels) {
    const text = truncate(label.sector === OTHER_FAMILY ? "AUTRES" : label.sector.toUpperCase(), maxChars);
    // Deux textes radiaux sont le plus proches à leur extrémité intérieure.
    const innerRadius = R_SECTOR_LABEL - text.length * MONO_RATIO * fontSize;
    const minGap = (fontSize * 1.1) / Math.max(innerRadius, fontSize);
    const clear = kept.every((other) => angleGap(label.angle, other.angle) >= Math.max(minGap, other.minGap));
    if (clear) kept.push({ ...label, text, minGap });
  }
  return { fontSize, labels: kept };
}

// Valeur la plus proche (en angle) du point touché, en unités du viewBox, ou
// `null` si le point est loin de l'anneau (centre du disque, coins).
export function nearestItem(items, x, y, scale) {
  const radius = Math.hypot(x - CX, y - CY);
  const tolerance = TAP_PX / scale;
  if (radius < R_TICK_IN - tolerance || radius > R_BAR + 100 * BAR_SCALE + tolerance) return null;
  const angle = Math.atan2(y - CY, x - CX);
  let best = null;
  for (const item of items) {
    if (!best || angleGap(item.angle, angle) < angleGap(best.angle, angle)) best = item;
  }
  return best;
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
        angle: mid,
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

