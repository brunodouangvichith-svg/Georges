import { decisionTagClass } from "../data";
import { dateFr, eur, nf, signed } from "../lib/format";

// Tableau des valeurs du CAC 40 (onglet "Trading"). C'est un instantané : il
// vient de `data.cac40` du dernier rapport stratégique
// (agents/strategic_report.py), d'où la date affichée — il ne change qu'à la
// génération d'un nouveau rapport depuis l'onglet "Rapport".

const changeColor = (value) => (value == null || value === 0 ? "var(--text-dim)" : value > 0 ? "var(--positive)" : "var(--negative)");

const COLUMNS = [
  { key: "name", label: "Valeur", render: (r) => <span title={r.symbol}>{r.name}</span> },
  { key: "sector", label: "Secteur" },
  { key: "close", label: "Clôture", align: "right", render: (r) => eur(r.close) },
  { key: "week_change_pct", label: "5 séances", align: "right", render: (r) => <span style={{ color: changeColor(r.week_change_pct) }}>{signed(r.week_change_pct)}</span> },
  { key: "decision_type", label: "Décision", render: (r) => (r.decision_type ? <span className={decisionTagClass(r.decision_type)}>{r.decision_type}</span> : "—") },
  { key: "confidence", label: "Confiance", align: "right", render: (r) => (r.confidence == null ? "—" : `${nf(r.confidence, 0)} %`) },
  { key: "pattern_type", label: "Figure" },
];

function Message({ children, color = "var(--text-dim)" }) {
  return (
    <div className="text-[12px]" style={{ color }}>
      {children}
    </div>
  );
}

export default function Cac40Panel({ query }) {
  const report = query.data;
  const rows = report?.data?.cac40 ?? [];
  return (
    <section aria-label="Valeurs du CAC 40" className="gd-panel min-w-0">
      <h2 className="display m-0 text-[14px] font-semibold">Valeurs du CAC 40{report ? ` (${rows.length})` : ""}</h2>
      {query.isLoading && <Message>Chargement…</Message>}
      {query.isError && <Message color="var(--negative)">Impossible de charger les valeurs du CAC 40.</Message>}
      {!query.isLoading && !query.isError && !report && (
        <Message>Aucune donnée pour l'instant : génère un rapport dans l'onglet « Rapport ».</Message>
      )}
      {report && (
        <>
          <Message>
            Données du rapport du {dateFr(report.created_at)}. Décision = dernière décision de George sur la valeur à cette date (figure détectée et
            confiance). Ce ne sont pas des recommandations personnalisées.
          </Message>
          {rows.length === 0 ? (
            <Message>Aucune valeur du CAC 40 en base.</Message>
          ) : (
            <div className="overflow-x-auto gd-scrollbar">
              <table className="w-full text-[12.5px] border-collapse" style={{ minWidth: 560 }}>
                <caption className="sr-only">Valeurs du CAC 40</caption>
                <thead>
                  <tr>
                    {COLUMNS.map((c) => (
                      <th key={c.key} scope="col" className={`py-1.5 px-2 font-medium border-b ${c.align === "right" ? "text-right" : "text-left"}`} style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.symbol}>
                      {COLUMNS.map((c) => (
                        <td key={c.key} className={`py-1.5 px-2 border-b ${c.align === "right" ? "text-right mono" : ""}`} style={{ borderColor: "var(--hairline)" }}>
                          {c.render ? c.render(row) : row[c.key] ?? "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
