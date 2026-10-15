import { useMemo } from "react";
import { buildChart, H, PAD_L, PAD_R, W } from "./bondChartLayout";

// Historique des rendements Obligataire Watch — une ligne par instrument,
// étiquetée directement en bout de courbe (pas de légende à décoder).
// Couleurs = variables du thème George (bleu/blanc/orange), jamais le vert
// ou le rouge, réservés au sens des variations dans le reste de l'écran.
// OAT/Bund sont des séries mensuelles (OCDE via FRED) : moins de points que
// les Treasuries quotidiens, c'est normal, pas un trou de données.

export default function BondHistoryChart({ series, rangeDays }) {
  const chart = useMemo(() => buildChart(series, rangeDays), [series, rangeDays]);

  if (!chart) {
    return (
      <div className="flex items-center justify-center text-[12px]" style={{ height: 240, color: "var(--text-dim)" }}>
        Pas encore d'historique sur cette période.
      </div>
    );
  }

  const summary = chart.lines.map((s) => `${s.label} ${s.lastValue.toFixed(2)} %`).join(", ");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Historique des rendements. Derniers points : ${summary}.`}
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      {chart.yTicks.map((t) => (
        <g key={t.v}>
          <line x1={PAD_L} x2={W - PAD_R} y1={t.y} y2={t.y} stroke="var(--hairline)" strokeWidth={1} />
          <text x={PAD_L - 6} y={t.y + 4} textAnchor="end" fontSize={10.5} fontFamily="IBM Plex Mono, monospace" fill="var(--text-dim)">
            {t.label}
          </text>
        </g>
      ))}
      {chart.xTicks.map((t) => (
        <text key={`${t.x}-${t.label}`} x={t.x} y={H - 8} textAnchor="middle" fontSize={10.5} fontFamily="IBM Plex Mono, monospace" fill="var(--text-dim)">
          {t.label}
        </text>
      ))}
      {chart.lines.map((s) => (
        <g key={s.key}>
          <path d={s.d} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.8} strokeDasharray={s.dash} strokeLinejoin="round" />
          <circle cx={s.lastX} cy={s.lastY} r={3} fill={s.color} />
          <text
            x={W - PAD_R + 8}
            y={chart.labelY[s.key] + 4}
            fontSize={11}
            fontFamily="IBM Plex Mono, monospace"
            fill={s.color}
            fontWeight={600}
          >
            {`${s.short} ${s.lastValue.toFixed(2)} %`}
          </text>
        </g>
      ))}
    </svg>
  );
}
