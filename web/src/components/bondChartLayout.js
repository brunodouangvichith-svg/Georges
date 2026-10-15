// Géométrie du graphique d'historique Obligataire Watch (voir
// BondHistoryChart.jsx) — séparée pour être testée seule et garder le fast refresh.

export const W = 760;
export const H = 340;
export const PAD_L = 44;
export const PAD_R = 132;
const PAD_T = 16;
const PAD_B = 28;
const LABEL_GAP = 14;

const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

function niceStep(span) {
  const raw = span / 5;
  const pow = 10 ** Math.floor(Math.log10(raw || 1));
  const n = raw / pow;
  return (n >= 5 ? 5 : n >= 2 ? 2 : n >= 1 ? 1 : 0.5) * pow;
}

export function buildChart(series, rangeDays, now = Date.now()) {
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
  const step = niceStep(vMax - vMin);
  vMin = Math.floor(vMin / step) * step;
  vMax = Math.ceil(vMax / step) * step;

  const x = (t) => PAD_L + ((t - tMin) / (tMax - tMin || 1)) * (W - PAD_L - PAD_R);
  const y = (v) => PAD_T + (1 - (v - vMin) / (vMax - vMin || 1)) * (H - PAD_T - PAD_B);

  const yTicks = [];
  for (let v = vMin; v <= vMax + step / 2; v += step) yTicks.push({ v, y: y(v), label: `${v.toFixed(step < 1 ? 1 : 0)} %` });

  // Repères de date : premier jour de chaque mois (ou de chaque année si la
  // plage est longue), au plus ~7 repères.
  const xTicks = [];
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

