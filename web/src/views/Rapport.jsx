import { useEffect, useMemo, useRef, useState } from "react";
import MarkdownText from "../components/MarkdownText";
import { decisionTagClass } from "../data";
import { useGenerateStrategicReport, useStrategicReport, useStrategicReports } from "../api/queries";

// Onglet "Rapport" — Rapport stratégique hebdomadaire (France, marchés,
// CAC 40), voir agents/strategic_report.py. Tous les chiffres affichés ici
// viennent de `report.data` (calculés en Python par George) ; seul le
// commentaire (`narrative_markdown`) est rédigé par le LLM. Le portefeuille
// virtuel est une simulation : aucun ordre n'est jamais transmis.

const RISK = {
  vert: { label: "VERT", color: "var(--positive)", text: "Détente : spread et OAT sous les seuils de vigilance." },
  orange: { label: "ORANGE", color: "var(--warning)", text: "Vigilance : tensions élevées, sans signal de crise de financement." },
  rouge: { label: "ROUGE", color: "var(--negative)", text: "Alerte : OAT et spread au-delà des seuils de tension." },
  indetermine: { label: "INDÉTERMINÉ", color: "var(--text-dim)", text: "Données obligataires insuffisantes pour conclure." },
};

const nf = (value, digits = 2) =>
  value == null ? "—" : Number(value).toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const eur = (value) => (value == null ? "—" : `${nf(value)} €`);
const signed = (value, unit = " %", digits = 2) => (value == null ? "—" : `${value > 0 ? "+" : ""}${nf(value, digits)}${unit}`);
const pnlColor = (value) => (value == null || value === 0 ? "var(--text-dim)" : value > 0 ? "var(--positive)" : "var(--negative)");
const dateFr = (iso) => (iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" }) : "—");
const dateTimeFr = (iso) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

function Panel({ title, children, right, className = "" }) {
  return (
    <section aria-label={title} className={`border rounded-[10px] p-3.5 flex flex-col gap-2.5 min-w-0 ${className}`} style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
      <div className="flex items-center justify-between gap-2">
        <h2 className="m-0 text-[10.5px] uppercase tracking-wider font-medium" style={{ color: "var(--text-dim)" }}>
          {title}
        </h2>
        {right}
      </div>
      {children}
    </section>
  );
}

function Kpi({ label, value, sub, color }) {
  return (
    <div className="border rounded-[10px] p-3 flex flex-col gap-1 min-w-0" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
      <div className="text-[10.5px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="mono text-[20px] font-bold" style={{ color: color ?? "var(--text)" }}>
        {value}
      </div>
      {sub && (
        <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function Table({ caption, columns, rows, empty }) {
  if (!rows.length) {
    return (
      <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
        {empty}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto gd-scrollbar">
      <table className="w-full text-[12.5px] border-collapse" style={{ minWidth: 560 }}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`py-1.5 px-2 font-medium border-b ${c.align === "right" ? "text-right" : "text-left"}`} style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.key ?? i}>
              {columns.map((c) => (
                <td key={c.key} className={`py-1.5 px-2 border-b ${c.align === "right" ? "text-right mono" : ""}`} style={{ borderColor: "var(--hairline)" }}>
                  {c.render ? c.render(row) : row[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Rapport() {
  const [selectedId, setSelectedId] = useState(null);
  const reports = useStrategicReports();
  const { data: report, isLoading, isError } = useStrategicReport(selectedId);
  const generate = useGenerateStrategicReport();
  const abortRef = useRef(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  function onGenerate() {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    generate.mutate(controller.signal, { onSuccess: () => setSelectedId(null) });
  }

  const data = report?.data;
  const risk = RISK[report?.risk_level] ?? RISK.indetermine;
  const sourceNumbers = useMemo(() => new Set((data?.sources ?? []).map((s) => s.n)), [data]);
  const brent = data?.energy?.find((e) => e.code === "BRENT_CRUDE_USD");
  const portfolio = data?.portfolio;

  return (
    <div className="h-full overflow-y-auto gd-scrollbar">
      <div className="mx-auto flex flex-col gap-4 px-5 py-4" style={{ maxWidth: 1440 }}>
        {/* En-tête */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="display m-0 text-[18px] font-semibold">Rapport stratégique</h1>
            <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
              France, marchés et CAC 40 · horizon 1 à 3 mois
              {report ? ` · rapport du ${dateFr(report.created_at)}` : ""}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {(reports.data ?? []).length > 0 && (
              <label className="flex items-center gap-2 text-[12px]" style={{ color: "var(--text-dim)" }}>
                Historique
                <select
                  value={selectedId ?? ""}
                  onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : null)}
                  className="rounded-lg border px-2 text-[12.5px]"
                  style={{ minHeight: 38, background: "var(--panel)", borderColor: "var(--hairline)", color: "var(--text)" }}
                >
                  <option value="">Dernier rapport</option>
                  {reports.data.map((r) => (
                    <option key={r.id} value={r.id}>
                      {dateTimeFr(r.created_at)} · {RISK[r.risk_level]?.label ?? r.risk_level}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              onClick={onGenerate}
              disabled={generate.isPending}
              className="text-[12.5px] font-semibold rounded-lg px-3.5"
              style={{ minHeight: 38, background: "var(--accent)", color: "#fff", opacity: generate.isPending ? 0.7 : 1 }}
            >
              {generate.isPending ? "Génération… (1 à 3 min)" : "Générer le rapport de la semaine"}
            </button>
          </div>
        </div>

        {generate.isError && generate.error?.name !== "AbortError" && (
          <div role="alert" className="text-[13px] p-3 rounded-lg border" style={{ borderColor: "var(--negative)", color: "var(--negative)" }}>
            {generate.error.message}
          </div>
        )}
        {isError && (
          <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
            Impossible de contacter l'API — le serveur met parfois 1 à 2 minutes à se réveiller, réessaie dans un instant.
          </div>
        )}
        {isLoading && (
          <div className="text-[13px]" style={{ color: "var(--text-dim)" }}>
            Chargement du rapport…
          </div>
        )}
        {!isLoading && !isError && !report && (
          <Panel title="Aucun rapport">
            <div className="text-[13px]">
              Aucun rapport n'a encore été généré. Clique sur « Générer le rapport de la semaine » : George rassemble ses données
              (obligations, énergie, décisions sur le CAC 40), cherche l'actualité de la semaine et rédige le rapport.
            </div>
          </Panel>
        )}

        {data && (
          <>
            {/* Indicateur de risque */}
            <section aria-label="Risque obligataire français" className="border rounded-[10px] p-4 flex flex-wrap items-center gap-4" style={{ borderColor: risk.color, background: "var(--panel)" }}>
              <div className="flex flex-col gap-1">
                <div className="text-[10.5px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
                  Risque obligataire français
                </div>
                <div className="mono text-[24px] font-bold" style={{ color: risk.color }}>
                  {risk.label}
                </div>
              </div>
              <div className="flex-1 min-w-[240px] text-[13px]">
                <div>{risk.text}</div>
                <div className="text-[11.5px] mt-1" style={{ color: "var(--text-dim)" }}>
                  Seuils de suivi de ce rapport, pas des seuils officiels : rouge si {data.risk.criteria.rouge} ; vert si {data.risk.criteria.vert}.
                </div>
              </div>
            </section>

            {/* Chiffres clés */}
            <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))" }}>
              <Kpi
                label="CAC 40"
                value={data.cac40_index ? nf(data.cac40_index.close) : "—"}
                sub={data.cac40_index ? `${signed(data.cac40_index.week_change_pct)} sur 5 séances · clôture du ${dateFr(data.cac40_index.as_of)}` : "Clôture indisponible"}
                color={data.cac40_index ? undefined : "var(--text-dim)"}
              />
              <Kpi label="OAT France 10 ans" value={data.risk.oat_10y_pct == null ? "—" : `${nf(data.risk.oat_10y_pct)} %`} sub={data.risk.oat_observed_at ? `Observé le ${dateFr(data.risk.oat_observed_at)}` : "Indisponible"} />
              <Kpi label="Spread OAT-Bund" value={data.risk.spread_oat_bund_bps == null ? "—" : `${signed(data.risk.spread_oat_bund_bps, " pb", 0)}`} sub={data.risk.bund_10y_pct == null ? "Bund indisponible" : `Bund 10 ans ${nf(data.risk.bund_10y_pct)} %`} />
              <Kpi label="Brent" value={brent ? `${nf(brent.price)} $` : "—"} sub={brent ? `Au ${dateFr(brent.as_of)}${brent.change_24h_pct == null ? "" : ` · ${signed(brent.change_24h_pct)} sur 24 h`}` : "Indisponible"} />
            </div>

            {/* Commentaire */}
            <Panel title="Analyse de George" right={report.model_used ? <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>Rédigé par {report.model_used}</span> : null}>
              <MarkdownText markdown={report.narrative_markdown} sourceNumbers={sourceNumbers} />
            </Panel>

            {/* Portefeuille virtuel */}
            {portfolio && (
              <Panel title="Portefeuille virtuel — simulation">
                <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                  Capital initial {eur(portfolio.initial_capital)} · frais simulés {nf(portfolio.fee_rate * 100, 2)} % par ordre · réserve de liquidités minimale {nf(portfolio.min_cash_ratio * 100, 0)} %
                  · prix de référence : clôtures au {dateFr(data.prices_as_of)}. Aucun ordre réel n'est passé.
                </div>
                <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
                  <Kpi label="Valeur totale" value={eur(portfolio.total_value)} />
                  <Kpi label="Liquidités" value={eur(portfolio.cash)} sub={portfolio.total_value ? `${nf((portfolio.cash / portfolio.total_value) * 100, 1)} % du total` : null} />
                  <Kpi label="Depuis le départ" value={signed(portfolio.performance_since_start_pct)} color={pnlColor(portfolio.performance_since_start_pct)} />
                  <Kpi label="Depuis le rapport précédent" value={signed(portfolio.performance_since_previous_pct)} color={pnlColor(portfolio.performance_since_previous_pct)} sub={portfolio.previous_total_value == null ? "Premier rapport" : `vs ${dateTimeFr(portfolio.previous_valued_at)}`} />
                  <Kpi label="Frais cumulés" value={eur(portfolio.fees_total)} />
                </div>
                <h3 className="m-0 mt-1 text-[12.5px] font-semibold">Ordres simulés de ce rapport</h3>
                <Table
                  caption="Ordres simulés"
                  empty="Aucun ordre cette semaine : aucun signal nouveau ne justifiait d'achat ou de vente."
                  rows={portfolio.trades.map((t) => ({ ...t, key: `${t.symbol}-${t.side}` }))}
                  columns={[
                    { key: "name", label: "Valeur" },
                    { key: "side", label: "Sens", render: (r) => <span style={{ color: r.side === "achat" ? "var(--positive)" : "var(--negative)" }}>{r.side === "achat" ? "Achat" : "Vente"}</span> },
                    { key: "quantity", label: "Quantité", align: "right" },
                    { key: "price", label: "Prix", align: "right", render: (r) => eur(r.price) },
                    { key: "gross", label: "Montant", align: "right", render: (r) => eur(r.gross) },
                    { key: "fees", label: "Frais", align: "right", render: (r) => eur(r.fees) },
                    { key: "rationale", label: "Justification" },
                  ]}
                />
                <h3 className="m-0 mt-1 text-[12.5px] font-semibold">Positions</h3>
                {portfolio.positions.some((p) => p.price_stale) && (
                  <div className="text-[11.5px]" style={{ color: "var(--warning)" }}>
                    * Cours périmé (flux de prix arrêté) : la position est valorisée à sa dernière clôture connue et n'est ni achetée ni vendue tant que le prix n'est pas à jour.
                  </div>
                )}
                <Table
                  caption="Positions du portefeuille virtuel"
                  empty="Aucune position : tout est en liquidités."
                  rows={portfolio.positions.map((p) => ({ ...p, key: p.symbol }))}
                  columns={[
                    { key: "name", label: "Valeur" },
                    { key: "quantity", label: "Quantité", align: "right" },
                    {
                      key: "price",
                      label: "Cours",
                      align: "right",
                      render: (r) => (
                        <span title={r.price_stale ? `Dernière clôture connue : ${dateFr(r.price_as_of)}` : undefined}>
                          {eur(r.price)}
                          {r.price_stale ? " *" : ""}
                        </span>
                      ),
                    },
                    { key: "value", label: "Valeur", align: "right", render: (r) => eur(r.value) },
                    { key: "weight_pct", label: "Poids", align: "right", render: (r) => (r.weight_pct == null ? "—" : `${nf(r.weight_pct, 1)} %`) },
                  ]}
                />
              </Panel>
            )}

            {/* 40 valeurs */}
            <Panel title={`Valeurs du CAC 40 (${data.cac40?.length ?? 0})`}>
              <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                Décision = dernière décision ouverte de George sur la valeur (figure détectée et confiance). Ce ne sont pas des recommandations personnalisées.
              </div>
              <Table
                caption="Valeurs du CAC 40"
                empty="Aucune valeur du CAC 40 en base."
                rows={(data.cac40 ?? []).map((r) => ({ ...r, key: r.symbol }))}
                columns={[
                  { key: "name", label: "Valeur", render: (r) => <span title={r.symbol}>{r.name}</span> },
                  { key: "sector", label: "Secteur" },
                  { key: "close", label: "Clôture", align: "right", render: (r) => eur(r.close) },
                  { key: "week_change_pct", label: "5 séances", align: "right", render: (r) => <span style={{ color: pnlColor(r.week_change_pct) }}>{signed(r.week_change_pct)}</span> },
                  { key: "decision_type", label: "Décision", render: (r) => (r.decision_type ? <span className={decisionTagClass(r.decision_type)}>{r.decision_type}</span> : "—") },
                  { key: "confidence", label: "Confiance", align: "right", render: (r) => (r.confidence == null ? "—" : `${nf(r.confidence, 0)} %`) },
                  { key: "pattern_type", label: "Figure" },
                  { key: "portfolio_action", label: "Portefeuille" },
                ]}
              />
            </Panel>

            {/* Sources */}
            <Panel title={`Sources web (${data.sources?.length ?? 0})`}>
              {(data.sources ?? []).length === 0 ? (
                <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucune source web récupérée pour ce rapport : le commentaire ne s'appuie que sur les données de George.
                </div>
              ) : (
                <ol className="m-0 pl-0 list-none flex flex-col gap-1.5 text-[12.5px]">
                  {data.sources.map((s) => (
                    <li key={s.n} id={`source-${s.n}`} className="flex gap-2">
                      <span className="mono" style={{ color: "var(--text-dim)" }}>
                        [{s.n}]
                      </span>
                      <span>
                        <a href={s.url} target="_blank" rel="noreferrer noopener" style={{ color: "var(--accent)" }}>
                          {s.titre}
                        </a>{" "}
                        <span style={{ color: "var(--text-dim)" }}>· {s.theme}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>

            <div className="text-[11.5px] pb-2" style={{ color: "var(--text-dim)" }}>
              Rapport généré le {dateTimeFr(data.generated_at)}. Les chiffres viennent de la base de George et des sources citées ; le commentaire est rédigé par un modèle de langue à partir de ces seules données. Ce n'est pas un conseil en investissement.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
