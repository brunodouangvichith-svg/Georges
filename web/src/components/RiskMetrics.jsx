import { dateFr, nf } from "../lib/format";

// Liquidité et risque de la valeur sélectionnée. Tous les chiffres sont
// calculés par l'API (engine/risk_metrics.py) ; « — » = historique insuffisant
// ou référence indisponible.

const percent = (value, digits = 1) => (value == null ? "—" : `${nf(value, digits)} %`);

// Le tiret seul est souvent passé sous silence par un lecteur d'écran.
const missing = (
  <>
    <span aria-hidden="true">—</span>
    <span className="sr-only">non disponible</span>
  </>
);

export default function RiskMetrics({ metrics, index, loading, error }) {
  const indexName = index?.name ?? "CAC 40";
  const rows = [
    [
      "Volume quotidien moyen (20 séances)",
      metrics?.average_daily_volume == null ? "—" : `${nf(metrics.average_daily_volume, 0)} titres`,
    ],
    ["Volatilité réalisée annualisée (1 an)", percent(metrics?.volatility_pct)],
    ["ATR (14 séances)", metrics?.atr == null ? "—" : `${nf(metrics.atr)} € (${percent(metrics.atr_pct)} du cours)`],
    [`Bêta (β) / ${indexName} (1 an)`, nf(metrics?.beta)],
    [`Corrélation / ${indexName} (1 an)`, nf(metrics?.index_correlation)],
    [
      metrics?.sector_correlation == null
        ? "Corrélation / secteur (1 an)"
        : `Corrélation / secteur ${metrics.sector_family} (1 an, ${metrics.sector_peers} autres valeurs)`,
      nf(metrics?.sector_correlation),
    ],
  ];

  return (
    <div className="flex flex-col gap-1">
      <h3 className="gd-label m-0">Liquidité et risque</h3>
      {loading || error ? (
        <div role="status" className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
          {loading ? "Calcul des mesures…" : "Mesures de risque indisponibles."}
        </div>
      ) : (
        <>
          <dl className="m-0 grid gap-x-3 gap-y-1 text-[11.5px]" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
            {rows.map(([label, value]) => (
              <div key={label} className="contents">
                <dt style={{ color: "var(--text-dim)" }}>{label}</dt>
                <dd className="m-0 text-right font-semibold">{value === "—" ? missing : value}</dd>
              </div>
            ))}
          </dl>
          {metrics?.suspect_jump_date && (
            <p className="m-0 text-[11px]" style={{ color: "var(--warning)" }}>
              Variation de plus de 50 % en une séance le {dateFr(metrics.suspect_jump_date)} : à vérifier (opération sur
              titres possible), les mesures sur un an peuvent être faussées.
            </p>
          )}
          {index && !index.available && (
            <p className="m-0 text-[11px]" style={{ color: "var(--text-dim)" }}>
              Cours du {indexName} indisponibles : bêta et corrélation avec l'indice non calculés.
            </p>
          )}
          <p className="m-0 text-[11px]" style={{ color: "var(--text-dim)" }}>
            {metrics?.as_of ? `Cours jusqu'au ${dateFr(metrics.as_of)}` : "Aucun cours exploitable"}
            {index?.available && ` · ${indexName} (Yahoo Finance) jusqu'au ${dateFr(index.as_of)}`} · non ajustés des
            dividendes · « — » : données insuffisantes
          </p>
        </>
      )}
    </div>
  );
}
