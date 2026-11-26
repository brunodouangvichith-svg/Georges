// Géométrie du tore 3D de l'écran Univers (voir UniversTorus.jsx) — séparée
// du composant pour pouvoir être testée seule et garder le fast refresh.

export const RING = 1; // rayon de l'anneau (centre → axe du tube)
export const TUBE = 0.62; // rayon du tube
const SPIKE_MIN = 0.07; // antenne d'une valeur sans figure détectée
const SPIKE_SPAN = 0.5; // longueur ajoutée à 100 % de confiance
export const MAX_RADIUS = RING + TUBE + SPIKE_MIN + SPIKE_SPAN;
const CAMERA = 5.2; // distance de la caméra (perspective)
const TAP_PX = 22; // tolérance d'un clic ou d'un toucher
const SECTOR_GAP = 2; // places vides entre deux familles de secteur
const MIN_FAMILY_SIZE = 3;

export function torusPoint(u, v, radius = TUBE) {
  const d = RING + radius * Math.cos(v);
  return [d * Math.cos(u), d * Math.sin(u), radius * Math.sin(v)];
}

function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Fils décoratifs : des hélices enroulées sur le tube, à graine fixe. Ils ne
// représentent aucune donnée.
export function buildStrands(count = 300, steps = 48) {
  const rand = seeded(42);
  return Array.from({ length: count }, () => {
    const u0 = rand() * Math.PI * 2;
    const v0 = rand() * Math.PI * 2;
    const sweep = (0.5 + rand() * 1.6) * (rand() < 0.5 ? -1 : 1);
    const turns = 0.6 + rand() * 1.4;
    const radius = TUBE * (0.86 + rand() * 0.18);
    return Array.from({ length: steps + 1 }, (_, i) => {
      const t = i / steps;
      return torusPoint(u0 + sweep * t, v0 + turns * Math.PI * 2 * t, radius);
    });
  });
}

// Les valeurs sont rangées autour de l'anneau par grande famille de secteur
// (la partie avant " / " : "Santé / Biotechnologie" et "Santé / Pharmacie" →
// "Santé"), la plus grosse d'abord, avec un écart entre deux familles. Les
// familles de moins de MIN_FAMILY_SIZE valeurs sont réunies en fin d'anneau.
const sectorFamily = (sector) => (sector || "Autre").split(" / ")[0].trim() || "Autre";

export function buildItems(securities, patternsBySymbol, decisionsMap) {
  const families = new Map();
  for (const security of securities) {
    const key = sectorFamily(security.sector);
    if (!families.has(key)) families.set(key, []);
    families.get(key).push(security);
  }
  const all = [...families.values()];
  const groups = all.filter((list) => list.length >= MIN_FAMILY_SIZE).sort((a, b) => b.length - a.length);
  const others = all.filter((list) => list.length < MIN_FAMILY_SIZE).flat();
  if (others.length) groups.push(others);
  const slots = securities.length + groups.length * SECTOR_GAP;
  const step = slots > 0 ? (Math.PI * 2) / slots : 0;

  let slot = 0;
  return groups.flatMap((list) => {
    const items = list.map(({ symbol, name }) => {
      const pattern = patternsBySymbol?.[symbol] ?? null;
      return {
        symbol,
        name,
        angle: -Math.PI / 2 + slot++ * step,
        confidence: pattern ? Math.max(0, Math.min(100, pattern.confidence)) : null,
        decision: decisionsMap?.[symbol]?.decision_type ?? null,
      };
    });
    slot += SECTOR_GAP;
    return items;
  });
}

// Une valeur = une boucle autour du tube et une antenne sur le bord extérieur.
// La longueur de l'antenne suit la confiance de la dernière figure détectée
// (`items` vient de buildItems).
export function buildFilaments(items, steps = 36) {
  return items.map((item) => {
    const length = SPIKE_MIN + ((item.confidence ?? 0) / 100) * SPIKE_SPAN;
    return {
      ...item,
      loop: Array.from({ length: steps + 1 }, (_, i) => torusPoint(item.angle, (i / steps) * Math.PI * 2)),
      base: torusPoint(item.angle, 0),
      tip: torusPoint(item.angle, 0, TUBE + length),
    };
  });
}

// Projette un point 3D à l'écran : le tore tourne sur son propre axe, celui
// qui traverse le trou (`spin`) ; la vue est ensuite inclinée (`yaw` autour de
// la verticale, `tilt` autour de l'horizontale), puis mise en perspective. À
// vue fixe, l'axe ne bouge donc pas à l'écran. `depth` croît vers
// l'observateur.
// `left` : abscisse de la zone du tore quand une liste occupe sa gauche.
export function makeProjector({ spin = 0, yaw, tilt, width, height, left = 0 }) {
  const cs = Math.cos(spin);
  const ss = Math.sin(spin);
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cx = Math.cos(tilt);
  const sx = Math.sin(tilt);
  // La marge couvre le grossissement dû à la perspective.
  const scale = (Math.min(width, height) / 2 / MAX_RADIUS) * 0.86;
  return ([px, py, z]) => {
    const x = px * cs - py * ss;
    const y = px * ss + py * cs;
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    const y2 = y * cx - z1 * sx;
    const depth = y * sx + z1 * cx;
    const k = (CAMERA / (CAMERA - depth)) * scale;
    return { x: left + width / 2 + x1 * k, y: height / 2 + y2 * k, depth };
  };
}

// Fenêtre de `count` éléments sur une liste parcourue en boucle : à chaque pas,
// l'élément précédent de la liste entre par le haut et celui du bas sort (au
// premier pas, le dernier de la liste). Sans défilement si tout tient.
function loopWindow(all, count, step) {
  const total = all.length;
  const start = total > count ? (total - (step % total)) % total : 0;
  return Array.from({ length: Math.min(count, total) }, (_, i) => all[(start + i) % total]);
}

// Cartes du fil affiché à côté du tore : les décisions enregistrées des valeurs
// suivies (la dernière de chaque valeur), la plus récente en premier. Au-delà de
// `count`, le fil défile en boucle (loopWindow ; au premier pas, la plus
// ancienne entre). Aucune décision n'est inventée ni redatée.
export function buildCards(items, decisionsMap, count = 10, step = 0) {
  const bySymbol = new Map(items.map((item) => [item.symbol, item]));
  const all = Object.values(decisionsMap ?? {})
    .filter((decision) => bySymbol.has(decision.symbol))
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return loopWindow(all, count, step).map((decision) => ({ ...bySymbol.get(decision.symbol), detail: decision }));
}

// Cartes de la liste des meilleures figures : la dernière figure de chaque
// valeur suivie, classées par confiance (à égalité, la plus récente d'abord),
// avec leur rang. Même défilement en boucle que les décisions.
export function buildPatternCards(items, patternsBySymbol, count = 10, step = 0) {
  const all = items
    .filter((item) => patternsBySymbol?.[item.symbol])
    .map((item) => ({ ...item, detail: patternsBySymbol[item.symbol] }))
    .sort(
      (a, b) =>
        b.confidence - a.confidence ||
        String(b.detail.detected_at).localeCompare(String(a.detail.detected_at)) ||
        a.symbol.localeCompare(b.symbol)
    )
    .map((card, i) => ({ ...card, rank: i + 1 }));
  return loopWindow(all, count, step);
}

// Valeur dont l'antenne (son extrémité) est la plus proche du point cliqué,
// ou `null` si aucune n'est à portée. À distance égale, celle de devant.
export function nearestFilament(filaments, project, px, py) {
  let best = null;
  let bestScore = Infinity;
  for (const filament of filaments) {
    const { x, y, depth } = project(filament.tip);
    const distance = Math.hypot(x - px, y - py);
    // La profondeur ne pèse que quelques pixels : elle départage deux
    // antennes superposées à l'écran.
    const score = distance - depth * 2;
    if (distance <= TAP_PX && score < bestScore) {
      best = filament;
      bestScore = score;
    }
  }
  return best;
}
