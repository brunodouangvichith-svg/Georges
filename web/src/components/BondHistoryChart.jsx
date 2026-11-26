import { useMemo } from "react";
import { useElementWidth } from "../hooks/useElementWidth";
import { buildChart, layoutFor, WIDE } from "./bondChartLayout";

// Historique des rendements Obligataire Watch — une ligne par instrument,
// étiquetée directement en bout de courbe (pas de légende à décoder).
// Couleurs = variables du thème George (bleu/blanc/orange), jamais le vert
// ou le rouge, réservés au sens des variations dans le reste de l'écran.
// OAT/Bund sont des séries mensuelles (OCDE via FRED) : moins de points que
// les Treasuries quotidiens, c'est normal, pas un trou de données.

// Dans un cadre étroit (téléphone), voir `layoutFor` : les étiquettes de fin
// de courbe passent dans une légende sous le graphique.

export default function BondHistoryChart({ series, rangeDays }) {
  const [ref, containerWidth] = useElementWidth();
  const layout = useMemo(() => layoutFor(containerWidth), [containerWidth]);
  const narrow = layout !== WIDE;
  const chart = useMemo(() => buildChart(series, rangeDays, Date.now(), layout), [series, rangeDays, layout]);

  if (!chart) {
    return (
      <div ref={ref} className="flex items-center justify-center text-[12px]" style={{ height: 240, color: "var(--text-dim)" }}>
        Pas encore d'historique sur cette période.
      </div>
    );
  }

  const summary = chart.lines.map((s) => `${s.label} ${s.lastValue.toFixed(2)} %`).join(", ");

  const { width, height, padL, padR } = layout;
  const fontSize = narrow ? 11 : 10.5;

  return (
    <div ref={ref}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Historique des rendements. Derniers points : ${summary}.`}
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        {chart.yTicks.map((t) => (
          <g key={t.v}>
            <line x1={padL} x2={width - padR} y1={t.y} y2={t.y} stroke="var(--hairline)" strokeWidth={1} />
            <text x={padL - 6} y={t.y + 4} textAnchor="end" fontSize={fontSize} fontFamily="IBM Plex Mono, monospace" fill="var(--text-dim)">
              {t.label}
            </text>
          </g>
        ))}
        {chart.xTicks.map((t) => (
          <text key={`${t.x}-${t.label}`} x={t.x} y={height - 8} textAnchor="middle" fontSize={fontSize} fontFamily="IBM Plex Mono, monospace" fill="var(--text-dim)">
            {t.label}
          </text>
        ))}
        {chart.lines.map((s) => (
          <g key={s.key}>
            <path d={s.d} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.8} strokeDasharray={s.dash} strokeLinejoin="round" />
            <circle cx={s.lastX} cy={s.lastY} r={3} fill={s.color} />
            {!narrow && (
              <text
                x={width - padR + 8}
                y={chart.labelY[s.key] + 4}
                fontSize={11}
                fontFamily="IBM Plex Mono, monospace"
                fill={s.color}
                fontWeight={600}
              >
                {`${s.short} ${s.lastValue.toFixed(2)} %`}
              </text>
            )}
          </g>
        ))}
      </svg>
      {narrow && (
        <ul
          role="list"
          aria-label="Dernières valeurs"
          className="mono m-0 mt-2 grid list-none gap-x-3 gap-y-1 p-0 text-[12px]"
          style={{ gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))" }}
        >
          {chart.lines.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              {/* Même trait (couleur, épaisseur, pointillés) que la courbe. */}
              <svg width={20} height={8} aria-hidden="true" className="shrink-0">
                <line x1={0} x2={20} y1={4} y2={4} stroke={s.color} strokeWidth={s.width ?? 1.8} strokeDasharray={s.dash} />
              </svg>
              <span>{`${s.short} ${s.lastValue.toFixed(2)} %`}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
