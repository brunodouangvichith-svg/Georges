import { useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { useBaskets, useDecisions, useGeorgeIndex, useSecurities } from "../api/queries";
import { decisionColor, scoreColor } from "../data";

const PIE_COLORS = ["#ffb020", "#3ddc84", "#5aa9ff", "#ff5c5c", "#c58aff", "#4fd6c5", "#e0975a", "#8b95a1", "#e85d9a", "#7fd6ff"];
const DECISION_TYPES = ["Achat", "Renforcer", "Surveiller", "Alléger"];
const CONFIDENCE_PRESETS = [0, 50, 60, 75];

const DECISION_COLUMNS = [
  { key: "symbol", label: "Ticker", defaultDir: "asc" },
  { key: "decision_type", label: "Décision", defaultDir: "asc" },
  { key: "entry_price", label: "Entrée", defaultDir: "desc" },
  { key: "take_profit", label: "Take-profit", defaultDir: "desc" },
  { key: "stop_loss", label: "Stop-loss", defaultDir: "desc" },
  { key: "confidence", label: "Confiance", defaultDir: "desc" },
  { key: "created_at", label: "Créée le", defaultDir: "desc" },
];

function PerformanceBadge({ label, value }) {
  return (
    <span className="inline-flex items-baseline gap-0.5">
      <span style={{ color: "var(--text-dim)" }}>{label}</span>
      <span
        className="font-bold"
        style={{ color: value == null ? "var(--text-dim)" : value >= 0 ? "var(--positive)" : "var(--negative)" }}
      >
        {value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`}
      </span>
    </span>
  );
}

function BasketIndexRow({ basketId, basketName }) {
  const { data, isLoading } = useGeorgeIndex(basketId);
  const score = data?.george_index ?? null;

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span>{basketName}</span>
        <span className="font-bold" style={{ color: score != null ? scoreColor(score) : "var(--text-dim)" }}>
          {isLoading ? "…" : score != null ? Math.round(score) : "—"}
        </span>
      </div>
      <div className="rounded-full h-1.5" style={{ background: "var(--panel-alt)" }}>
        <div
          className="rounded-full h-1.5"
          style={{ width: `${score ?? 0}%`, background: score != null ? scoreColor(score) : "var(--hairline)" }}
        />
      </div>
      {!isLoading && (
        <div className="flex gap-3 mt-1.5 text-[11px] mono">
          <PerformanceBadge label="1j" value={data?.performance_1j} />
          <PerformanceBadge label="1s" value={data?.performance_1s} />
          <PerformanceBadge label="1m" value={data?.performance_1m} />
        </div>
      )}
    </div>
  );
}

export default function Paniers() {
  const { data: basketsPage, isLoading: basketsLoading, isError: basketsError } = useBaskets();
  const { data: securitiesPage, isError: securitiesError } = useSecurities({ limit: 200 });
  const { data: decisionsPage, isError: decisionsError } = useDecisions({ limit: 200 });
  const apiUnreachable = basketsError || securitiesError || decisionsError;

  const baskets = basketsPage ?? [];
  const securities = securitiesPage?.items ?? [];
  const decisions = decisionsPage?.items ?? [];

  const sectorAgg = useMemo(() => {
    const map = {};
    for (const s of securities) map[s.sector] = (map[s.sector] || 0) + 1;
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [securities]);

  const decisionCounts = useMemo(() => {
    const counts = {};
    for (const d of decisions) counts[d.decision_type] = (counts[d.decision_type] || 0) + 1;
    return counts;
  }, [decisions]);

  const [minConfidence, setMinConfidence] = useState(0);
  const [sortKey, setSortKey] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  function toggleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(DECISION_COLUMNS.find((c) => c.key === key).defaultDir);
    }
  }

  const visibleDecisions = useMemo(() => {
    const filtered = decisions.filter((d) => d.confidence >= minConfidence);
    const sign = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "string") return sign * va.localeCompare(vb);
      return sign * (va - vb);
    });
  }, [decisions, minConfidence, sortKey, sortDir]);

  return (
    <div className="h-full overflow-y-auto gd-scrollbar px-5 py-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
          <div>
            <div className="text-xs tracking-widest" style={{ color: "var(--warning)", letterSpacing: "0.2em" }}>
              GEORGE · PANIERS
            </div>
            <h1 className="display text-2xl sm:text-3xl font-bold mt-1">Paniers &amp; décisions</h1>
            <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>
              Univers suivi regroupé par panier — George Index calculé en temps réel depuis la base.
            </div>
          </div>
          <div className="flex gap-3 text-xs">
            {[
              ["Paniers", baskets.length, "var(--positive)"],
              ["Titres suivis", securities.length, "var(--warning)"],
              ["Décisions", decisions.length, "var(--text)"],
            ].map(([label, value, color]) => (
              <div key={label} className="px-3 py-2 rounded-lg border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
                <div style={{ color: "var(--text-dim)" }}>{label}</div>
                <div className="font-bold text-[15px]" style={{ color }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>

        {apiUnreachable && (
          <div
            className="text-[13px] p-4 rounded-lg border mb-6"
            style={{ borderColor: "var(--negative)", color: "var(--negative)" }}
          >
            Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
          </div>
        )}

        <div className="grid grid-cols-4 gap-3 mb-6">
          {DECISION_TYPES.map((status) => (
            <div key={status} className="rounded-lg p-3 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                {status}
              </div>
              <div className="font-bold" style={{ color: decisionColor(status) }}>
                {decisionCounts[status] ?? 0}
              </div>
            </div>
          ))}
        </div>

        <div className="grid lg:grid-cols-5 gap-5 mb-6">
          <div className="lg:col-span-2 rounded-lg p-4 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <div className="text-xs mb-3 tracking-wider" style={{ color: "var(--warning)" }}>
              GEORGE INDEX PAR PANIER
            </div>
            {basketsLoading && (
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                Chargement…
              </div>
            )}
            {!basketsLoading && baskets.length === 0 && (
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>
                Aucun panier. Lancez <code>python -m ingestion.seed_demo</code>.
              </div>
            )}
            <div className="space-y-3">
              {baskets.map((b) => (
                <BasketIndexRow key={b.id} basketId={b.id} basketName={b.name} />
              ))}
            </div>
          </div>

          <div className="lg:col-span-3 rounded-lg p-4 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <div className="text-xs mb-1 tracking-wider" style={{ color: "var(--warning)" }}>
              RÉPARTITION DE L'UNIVERS PAR SECTEUR
            </div>
            {sectorAgg.length === 0 ? (
              <div className="text-xs mt-3" style={{ color: "var(--text-dim)" }}>
                Aucun titre en base.
              </div>
            ) : (
              <>
                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={sectorAgg} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={1}>
                        {sectorAgg.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="var(--panel)" />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(v, n) => [`${v} titre${v > 1 ? "s" : ""}`, n]}
                        contentStyle={{ background: "var(--panel-alt)", border: "1px solid var(--hairline)", borderRadius: 6, fontSize: 12, color: "var(--text)" }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                  {sectorAgg.map((s, i) => (
                    <div key={s.name} className="flex items-center gap-1 text-xs" style={{ color: "var(--text-dim)" }}>
                      <span className="inline-block w-2 h-2 rounded-sm" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      {s.name} · {s.value}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="text-xs tracking-wider" style={{ color: "var(--warning)" }}>
            DÉCISIONS RÉCENTES
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span style={{ color: "var(--text-dim)" }}>Confiance minimale</span>
            {CONFIDENCE_PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setMinConfidence(p)}
                className="px-2.5 py-1 rounded-full border"
                style={{
                  background: minConfidence === p ? "var(--accent)" : "transparent",
                  borderColor: minConfidence === p ? "var(--accent)" : "var(--hairline)",
                  color: minConfidence === p ? "#fff" : "var(--text-dim)",
                }}
              >
                {p === 0 ? "Toutes" : `≥ ${p}%`}
              </button>
            ))}
          </div>
        </div>
        {decisions.length === 0 ? (
          <div className="text-xs" style={{ color: "var(--text-dim)" }}>
            Aucune décision enregistrée. Lancez <code>python -m engine.propose_decisions</code> ou <code>python -m ingestion.seed_demo</code>.
          </div>
        ) : visibleDecisions.length === 0 ? (
          <div className="text-xs" style={{ color: "var(--text-dim)" }}>
            Aucune décision avec une confiance ≥ {minConfidence}%.
          </div>
        ) : (
          <div className="rounded-lg overflow-hidden border" style={{ borderColor: "var(--hairline)" }}>
            <div className="overflow-x-auto gd-scrollbar">
              <table className="w-full text-xs" style={{ borderCollapse: "collapse", minWidth: 680 }}>
                <thead>
                  <tr style={{ background: "var(--panel-alt)", color: "var(--text-dim)" }}>
                    {DECISION_COLUMNS.map((c) => (
                      <th key={c.key} className="text-left px-3 py-2 font-normal border-b" style={{ borderColor: "var(--hairline)" }}>
                        <button
                          className="flex items-center gap-1"
                          style={{ color: sortKey === c.key ? "var(--text)" : "var(--text-dim)" }}
                          onClick={() => toggleSort(c.key)}
                        >
                          {c.label}
                          {sortKey === c.key && <span>{sortDir === "asc" ? "▲" : "▼"}</span>}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleDecisions.map((d, i) => (
                    <tr key={d.id} style={{ background: i % 2 === 0 ? "var(--bg)" : "var(--panel)" }}>
                      <td className="px-3 py-2 font-bold">{d.symbol}</td>
                      <td className="px-3 py-2">
                        <span className="font-bold" style={{ color: decisionColor(d.decision_type) }}>
                          {d.decision_type}
                        </span>
                      </td>
                      <td className="px-3 py-2">{d.entry_price.toFixed(2)} €</td>
                      <td className="px-3 py-2">{d.take_profit != null ? `${d.take_profit.toFixed(2)} €` : "—"}</td>
                      <td className="px-3 py-2">{d.stop_loss != null ? `${d.stop_loss.toFixed(2)} €` : "—"}</td>
                      <td className="px-3 py-2 font-bold" style={{ color: scoreColor(d.confidence) }}>
                        {Math.round(d.confidence)}%
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--text-dim)" }}>
                        {new Date(d.created_at).toLocaleDateString("fr-FR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="text-xs mt-5 pb-6" style={{ color: "var(--text-dim)" }}>
          Données réelles issues de l'API — la plupart des décisions ci-dessus viennent de figures chartistes réellement
          détectées (<code>engine.propose_decisions</code>, Phase 6) ; quelques-unes plus anciennes restent un jeu de
          démonstration illustratif (<code>ingestion/seed_demo.py</code>).
        </div>
      </div>
    </div>
  );
}
