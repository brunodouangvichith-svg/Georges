// Géométrie du graphique d'historique Obligataire Watch (voir
// BondHistoryChart.jsx) — séparée pour être testée seule et garder le fast refresh.

const PAD_T = 16;
const PAD_B = 28;
const LABEL_GAP = 14;

// Gabarit large : viewBox fixe mise à l'échelle, étiquettes en bout de courbe.
export const WIDE = { width: 760, height: 340, padL: 44, padR: 132, yDivisions: 5, xSpacing: null };

// Sous ce seuil, le gabarit large rendrait le texte illisible.
export const NARROW_BELOW = 560;

// Gabarit étroit : un viewBox à la taille réelle (le texte garde sa taille),
// plus haut en proportion, moins de graduations, et la légende des dernières
// valeurs sous le graphique au lieu de la marge droite.
export function layoutFor(containerWidth) {
  if (containerWidth == null || containerWidth >= NARROW_BELOW) return WIDE;
  return { width: containerWidth, height: 240, padL: 46, padR: 12, yDivisions: 3, xSpacing: 64 };
}

// Demi-largeur d'un repère de date (« janv. 26 » en 11 px à chasse fixe).
const X_LABEL_HALF = 27;

const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

function niceStep(span, divisions) {
  const raw = span / divisions;
  const pow = 10 ** Math.floor(Math.log10(raw || 1));
  const n = raw / pow;
  return (n >= 5 ? 5 : n >= 2 ? 2 : n >= 1 ? 1 : 0.5) * pow;
}

export function buildChart(series, rangeDays, now = Date.now(), layout = WIDE) {
  const { width, height, padL, padR, yDivisions, xSpacing } = layout;
  const from = now - rangeDays * 864e5;
  const lines = series
    .map((s) => ({
      ...s,
      points: (s.points ?? [])
        .map((p) => ({ t: Date.parse(p.observed_at), v: p.value_pct }))
        .filter((p) => Number.isFinite(p.t) && p.t >= from)
        .sort((a, b) => a.t - b.t),
    }))
    .filter((s) => s.points.length > 0);
  if (lines.length === 0) return null;

  const all = lines.flatMap((s) => s.points);
  const tMin = Math.min(...all.map((p) => p.t));
  const tMax = Math.max(...all.map((p) => p.t));
  let vMin = Math.min(...all.map((p) => p.v));
  let vMax = Math.max(...all.map((p) => p.v));
  if (vMax - vMin < 0.2) {
    vMin -= 0.1;
    vMax += 0.1;
  }
  const step = niceStep(vMax - vMin, yDivisions);
  vMin = Math.floor(vMin / step) * step;
  vMax = Math.ceil(vMax / step) * step;

  const x = (t) => padL + ((t - tMin) / (tMax - tMin || 1)) * (width - padL - padR);
  const y = (v) => PAD_T + (1 - (v - vMin) / (vMax - vMin || 1)) * (height - PAD_T - PAD_B);

  const yTicks = [];
  for (let v = vMin; v <= vMax + step / 2; v += step) yTicks.push({ v, y: y(v), label: `${v.toFixed(step < 1 ? 1 : 0)} %` });

  // Repères de date : premier jour de chaque mois (ou de chaque année si la
  // plage est longue), au plus ~7 repères.
  let xTicks = [];
  const monthsSpan = (tMax - tMin) / (30 * 864e5);
  const monthStep = monthsSpan > 36 ? 12 : monthsSpan > 14 ? 3 : monthsSpan > 6 ? 2 : 1;
  const start = new Date(tMin);
  let d = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
  while (d.getTime() <= tMax) {
    if (d.getUTCMonth() % monthStep === 0) {
      const label = monthStep === 12 ? String(d.getUTCFullYear()) : `${MONTHS[d.getUTCMonth()]} ${String(d.getUTCFullYear()).slice(2)}`;
      xTicks.push({ x: x(d.getTime()), label });
    }
    d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
  }

  // Gabarit étroit : aucun repère coupé par le bord droit, puis un repère
  // sur N pour qu'ils ne se touchent pas.
  if (xSpacing) {
    const inside = xTicks.filter((t) => t.x + X_LABEL_HALF <= width);
    const max = Math.max(1, Math.floor((width - padL - padR) / xSpacing));
    const every = Math.max(1, Math.ceil(inside.length / max));
    xTicks = inside.filter((_, i) => i % every === 0);
  }

  const drawn = lines.map((s) => {
    const last = s.points[s.points.length - 1];
    return {
      ...s,
      d: s.points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}`).join(""),
      lastX: x(last.t),
      lastY: y(last.v),
      lastValue: last.v,
    };
  });

  // Étiquettes en bout de courbe, écartées verticalement pour ne jamais se
  // chevaucher (tri par hauteur puis poussée vers le bas).
  const labels = [...drawn].sort((a, b) => a.lastY - b.lastY).map((s) => ({ key: s.key, y: s.lastY }));
  for (let i = 1; i < labels.length; i++) {
    if (labels[i].y - labels[i - 1].y < LABEL_GAP) labels[i].y = labels[i - 1].y + LABEL_GAP;
  }
  const labelY = Object.fromEntries(labels.map((l) => [l.key, l.y]));

  return { lines: drawn, yTicks, xTicks, labelY };
}

