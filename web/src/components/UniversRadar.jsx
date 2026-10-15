import { useMemo } from "react";
import { buildRadar, CX, CY, R_IN, R_TICK_IN, R_TICK_OUT, R_BAR, BAR_SCALE } from "./universRadarLayout";

// Radar de l'univers (écran Univers, thème Paper Lab).
//
// - Chaque trait autour du cercle = une valeur suivie, regroupées par
//   secteur (`securities.sector`, le plus gros secteur en premier).
// - La barre radiale = la confiance de la dernière figure détectée
//   (0-100 → 0-50 px) ; pas de barre = aucune figure. Trait épais au-delà de
//   75 %, pointillé quand la décision en cours est un allègement.
// - La valeur sélectionnée est surlignée et sa trajectoire de prix réelle
//   (les `closes` passés en prop) traverse le cercle, avec une perle toutes
//   les ~N séances et un double anneau sur la dernière.
// - Le champ de lignes à l'intérieur est purement décoratif (graine fixe,
//   aria-hidden) : il ne représente aucune donnée.
//
// Un clic sur un trait sélectionne la valeur. Ce n'est qu'un raccourci
// souris : la watchlist reste le chemin clavier/lecteur d'écran.

const W = 760;
const H = 680;

function seeded(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const f = (n) => n.toFixed(1);

// Calculé une seule fois : identique à chaque rendu.
const FLOW_D = (() => {
  const rand = seeded(42);
  let d = "";
  for (let i = 0; i < 150; i++) {
    const a0 = rand() * Math.PI * 2;
    const r0 = Math.sqrt(rand()) * R_IN;
    let x = CX + Math.cos(a0) * r0;
    let y = CY + Math.sin(a0) * r0;
    d += `M${f(x)} ${f(y)}`;
    const steps = 18 + Math.floor(rand() * 45);
    for (let s = 0; s < steps; s++) {
      const ang = Math.sin((x - CX) * 0.011) * 2.3 + Math.cos((y - CY) * 0.013) * 1.9 + (i % 3) * 0.5;
      x += Math.cos(ang) * 6;
      y += Math.sin(ang) * 6;
      if (Math.hypot(x - CX, y - CY) > R_IN - 2) break;
      d += `L${f(x)} ${f(y)}`;
    }
  }
  return d;
})();

function polar(angle, r) {
  return [CX + Math.cos(angle) * r, CY + Math.sin(angle) * r];
}

function segment(angle, r0, r1) {
  const [x0, y0] = polar(angle, r0);
  const [x1, y1] = polar(angle, r1);
  return `M${f(x0)} ${f(y0)}L${f(x1)} ${f(y1)}`;
}

function buildTrail(closes) {
  if (!closes || closes.length < 2) return { d: "", beads: [] };
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const n = closes.length;
  const x = (i) => CX - 220 + (i / (n - 1)) * 400;
  const y = (v) => CY + 150 - ((v - min) / span) * 150;
  const d = closes.map((v, i) => `${i ? "L" : "M"}${f(x(i))} ${f(y(v))}`).join("");
  const every = Math.max(1, Math.ceil(n / 14));
  const beads = [];
  for (let i = 0; i < n - 1; i += every) beads.push({ x: x(i), y: y(closes[i]), last: false });
  beads.push({ x: x(n - 1), y: y(closes[n - 1]), last: true });
  return { d, beads };
}

export default function UniversRadar({ securities, patternsBySymbol, decisionsMap, selectedSymbol, onSelect, closes }) {
  const { items, labels } = useMemo(
    () => buildRadar(securities, patternsBySymbol, decisionsMap),
    [securities, patternsBySymbol, decisionsMap]
  );
  const trail = useMemo(() => buildTrail(closes), [closes]);

  const paths = useMemo(() => {
    let ticks = "";
    let bars = "";
    let strong = "";
    let light = "";
    for (const it of items) {
      ticks += segment(it.angle, R_TICK_IN, R_TICK_OUT);
      if (it.confidence == null || it.symbol === selectedSymbol) continue;
      const seg = segment(it.angle, R_BAR, R_BAR + it.confidence * BAR_SCALE);
      if (it.lighten) light += seg;
      else if (it.confidence >= 75) strong += seg;
      else bars += seg;
    }
    return { ticks, bars, strong, light };
  }, [items, selectedSymbol]);

  const selected = items.find((it) => it.symbol === selectedSymbol) ?? null;
  const withPattern = items.filter((it) => it.confidence != null).length;
  const ariaLabel =
    `Radar de l'univers : ${items.length} valeurs réparties en ${labels.length} grands secteurs, ` +
    `${withPattern} avec une figure détectée. La longueur des barres suit la confiance de la figure.`;

  let selLabel = null;
  if (selected) {
    const [lx, ly] = polar(selected.angle, R_BAR + 52);
    const c = Math.cos(selected.angle);
    selLabel = {
      x: lx,
      y: ly + 4,
      anchor: c > 0.2 ? "start" : c < -0.2 ? "end" : "middle",
      text: `${selected.symbol} · ${selected.confidence == null ? "sans figure" : `${Math.round(selected.confidence)} %`}`,
    };
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel} style={{ width: "100%", height: "auto", display: "block" }}>
      <circle cx={CX} cy={CY} r={R_IN} fill="var(--panel)" />
      <path d={FLOW_D} fill="none" stroke="var(--text)" strokeWidth={0.55} strokeOpacity={0.3} aria-hidden="true" />
      {trail.d && (
        <g aria-hidden="true">
          <path d={trail.d} fill="none" stroke="var(--text)" strokeWidth={1} />
          {trail.beads.map((b, i) => (
            <circle
              key={i}
              cx={b.x}
              cy={b.y}
              r={b.last ? 6.5 : 3.6}
              fill="var(--bg)"
              stroke="var(--text)"
              strokeWidth={b.last ? 2 : 1}
            />
          ))}
        </g>
      )}
      <circle cx={CX} cy={CY} r={R_IN + 2} fill="none" stroke="var(--text)" strokeWidth={1.2} />
      <path d={paths.ticks} fill="none" stroke="var(--text)" strokeWidth={0.8} />
      <path d={paths.bars} fill="none" stroke="var(--text)" strokeWidth={1} strokeOpacity={0.55} />
      <path d={paths.strong} fill="none" stroke="var(--text)" strokeWidth={2.2} />
      <path d={paths.light} fill="none" stroke="var(--text)" strokeWidth={1.4} strokeDasharray="2 2" />
      {selected && (
        <path
          d={
            selected.confidence == null
              ? segment(selected.angle, R_TICK_IN - 4, R_TICK_OUT + 6)
              : segment(selected.angle, R_BAR, R_BAR + selected.confidence * BAR_SCALE)
          }
          fill="none"
          stroke="var(--text)"
          strokeWidth={4}
        />
      )}
      {labels.map((l) => (
        <text
          key={l.sector}
          x={l.x}
          y={l.y}
          textAnchor={l.anchor}
          fontFamily="IBM Plex Mono, monospace"
          fontSize={11}
          fontWeight={600}
          fill="var(--text)"
          stroke="var(--panel)"
          strokeWidth={4}
          paintOrder="stroke"
        >
          {l.text}
        </text>
      ))}
      {selLabel && (
        <text
          x={selLabel.x}
          y={selLabel.y}
          textAnchor={selLabel.anchor}
          fontFamily="IBM Plex Mono, monospace"
          fontSize={11.5}
          fontWeight={700}
          fill="var(--text)"
          stroke="var(--bg)"
          strokeWidth={4}
          paintOrder="stroke"
        >
          {selLabel.text}
        </text>
      )}
      {/* Zones de clic invisibles, une par valeur (souris uniquement). */}
      <g aria-hidden="true">
        {items.map((it) => {
          const [x0, y0] = polar(it.angle, R_TICK_IN - 6);
          const [x1, y1] = polar(it.angle, R_BAR + 54);
          return (
            <line
              key={it.symbol}
              x1={x0}
              y1={y0}
              x2={x1}
              y2={y1}
              stroke="transparent"
              strokeWidth={7}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(it.symbol)}
            >
              <title>{`${it.symbol} — ${it.name}`}</title>
            </line>
          );
        })}
      </g>
    </svg>
  );
}
