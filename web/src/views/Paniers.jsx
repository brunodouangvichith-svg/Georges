import { useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import Counter from "../components/Counter";
import ResponsePopup from "../components/ResponsePopup";
import {
  useBaskets,
  useCreatePortfolio,
  useDecisions,
  useExplainDecision,
  useGeorgeIndex,
  useSecurities,
} from "../api/queries";
import { decisionTagClass, scoreColor } from "../data";

const PIE_COLORS = ["#ffb020", "#3ddc84", "#5aa9ff", "#ff5c5c", "#c58aff", "#4fd6c5", "#e0975a", "#8b95a1", "#e85d9a", "#7fd6ff"];
const DECISION_TYPES = ["Achat", "Renforcer", "Surveiller", "Alléger"];
const CONFIDENCE_PRESETS = [0, 50, 60, 70, 75];
const DECISION_STATUSES = ["proposee", "confirmee", "sortie_proposee", "cloturee"];
const STATUS_LABELS = {
  proposee: "Proposée",
  confirmee: "Confirmée",
  sortie_proposee: "Sortie proposée",
  cloturee: "Clôturée",
};

const DECISION_COLUMNS = [
  { key: "symbol", label: "Ticker", defaultDir: "asc" },
  { key: "decision_type", label: "Décision", defaultDir: "asc" },
  { key: "status", label: "Statut", defaultDir: "asc" },
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
  const securities = useMemo(() => securitiesPage?.items ?? [], [securitiesPage]);
  const decisions = useMemo(() => decisionsPage?.items ?? [], [decisionsPage]);

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

  const [popup, setPopup] = useState(null);
  const explainMutation = useExplainDecision();

  // Sélection en attente de confirmation ("cocher" une ligne ne l'ajoute pas
  // tout de suite à un portefeuille) — vidée après enregistrement ou annulation.
  const [checkedIds, setCheckedIds] = useState(() => new Set());
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [portfolioName, setPortfolioName] = useState("");
  const createPortfolioMutation = useCreatePortfolio();

  function toggleChecked(id) {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function cancelCreatePortfolio() {
    setCreateModalOpen(false);
    setPortfolioName("");
  }

  function saveCreatePortfolio() {
    const name = portfolioName.trim();
    if (!name || checkedIds.size === 0) return;
    createPortfolioMutation.mutate(
      { name, decisionIds: [...checkedIds] },
      {
        onSuccess: () => {
          setCheckedIds(new Set());
          cancelCreatePortfolio();
        },
      }
    );
  }

  function openDecisionPopup(decision) {
    const title = `${decision.symbol} — ${decision.decision_type}`;
    setPopup({
      title,
      status: "prompt",
      text:
        `Entrée ${decision.entry_price.toFixed(2)} €` +
        (decision.take_profit != null ? ` · Take-profit ${decision.take_profit.toFixed(2)} €` : "") +
        (decision.stop_loss != null ? ` · Stop-loss ${decision.stop_loss.toFixed(2)} €` : "") +
        ` · Confiance ${Math.round(decision.confidence)}%`,
      actionLabel: "Demander une analyse à George",
      onAction: () => {
        setPopup((prev) => ({ ...prev, status: "loading", text: null }));
        explainMutation.mutate(
          { decisionId: decision.id },
          {
            onSuccess: (data) => setPopup({ title, status: "done", text: data.explanation }),
            onError: (err) => setPopup({ title, status: "error", text: err.message }),
          }
        );
      },
    });
  }

  const [minConfidence, setMinConfidence] = useState(0);
  const [decisionTypeFilter, setDecisionTypeFilter] = useState("Toutes");
  const [statusFilter, setStatusFilter] = useState("Toutes");
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
    const filtered = decisions.filter(
      (d) =>
        d.confidence >= minConfidence &&
        (decisionTypeFilter === "Toutes" || d.decision_type === decisionTypeFilter) &&
        (statusFilter === "Toutes" || d.status === statusFilter)
    );
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
  }, [decisions, minConfidence, decisionTypeFilter, statusFilter, sortKey, sortDir]);

  const typeColor = { Achat: "var(--positive)", Renforcer: "var(--positive)", Surveiller: "var(--warning)", Alléger: "var(--negative)" };
  const decisionTotal = Math.max(1, decisions.length);

  return (
    <div className="h-full overflow-y-auto gd-scrollbar">
      <ResponsePopup popup={popup} onClose={() => setPopup(null)} />
      {createModalOpen && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50 px-6"
          style={{ background: "rgba(0,0,0,0.55)" }}
          onClick={cancelCreatePortfolio}
        >
          <div
            className="max-w-sm w-full rounded-xl p-5 border"
            style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="display font-semibold text-[14px] mb-3" style={{ color: "var(--accent)" }}>
              Créer un portefeuille
            </div>
            <label className="text-[11px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
              Nom du portefeuille
            </label>
            <input
              autoFocus
              value={portfolioName}
              onChange={(e) => setPortfolioName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveCreatePortfolio()}
              placeholder="ex. Portefeuille croissance"
              className="w-full mt-1.5 mb-2 px-3 py-2 rounded-lg border text-[13px]"
              style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text)" }}
            />
            <div className="text-[11px] mb-4" style={{ color: "var(--text-dim)" }}>
              {checkedIds.size} décision{checkedIds.size > 1 ? "s" : ""} sélectionnée{checkedIds.size > 1 ? "s" : ""}
            </div>
            {createPortfolioMutation.isError && (
              <div className="text-[11.5px] mb-3" style={{ color: "var(--negative)" }}>
                {createPortfolioMutation.error.message}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={cancelCreatePortfolio}
                className="flex-1 py-2 rounded-lg border text-[13px] font-medium"
                style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
              >
                ❌ Annuler
              </button>
              <button
                onClick={saveCreatePortfolio}
                disabled={!portfolioName.trim() || createPortfolioMutation.isPending}
                className="flex-1 py-2 rounded-lg font-semibold text-[13px]"
                style={{ background: "var(--accent)", color: "#fff", opacity: portfolioName.trim() ? 1 : 0.5 }}
              >
                {createPortfolioMutation.isPending ? "…" : "✅ Enregistrer"}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="mx-auto flex flex-col gap-3.5 px-5 pt-4 pb-6" style={{ maxWidth: 1440 }}>
        {/* En-tête + compteurs (même disposition qu'Univers) */}
        <header className="flex flex-wrap items-start justify-between" style={{ gap: "16px 40px" }}>
          <div className="flex flex-col gap-1" style={{ minWidth: 260 }}>
            <h1 className="display m-0 text-[20px] font-semibold">
              George / <span>Paniers</span>
            </h1>
            <div className="gd-label">Paniers &amp; décisions → George Index en temps réel</div>
          </div>
          <div className="flex flex-wrap justify-end" style={{ gap: "14px 28px", flex: "1 1 600px" }}>
            <Counter label="Paniers" value={baskets.length} ratio={1} />
            <Counter label="Titres suivis" value={securities.length} ratio={1} />
            <Counter label="Décisions" value={decisions.length} ratio={1} />
            {DECISION_TYPES.map((t) => (
              <Counter
                key={t}
                label={t}
                value={decisionCounts[t] ?? 0}
                ratio={(decisionCounts[t] ?? 0) / decisionTotal}
                color={typeColor[t]}
              />
            ))}
          </div>
        </header>

        {/* Barre d'actions */}
        <div
          className="flex flex-wrap items-center gap-2.5 pt-2 text-[11px]"
          style={{ borderTop: "1px solid var(--hairline)", color: "var(--text-dim)" }}
        >
          <span>
            {visibleDecisions.length} décision{visibleDecisions.length > 1 ? "s" : ""} affichée
            {visibleDecisions.length > 1 ? "s" : ""} sur {decisions.length}
          </span>
          <div className="ml-auto flex flex-wrap gap-1.5">
            {checkedIds.size > 0 && (
              <button onClick={() => setCreateModalOpen(true)} className="gd-btn gd-btn--solid">
                Créer un portefeuille ({checkedIds.size})
              </button>
            )}
          </div>
        </div>

        {apiUnreachable && (
          <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--negative)", color: "var(--negative)" }}>
            Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
          </div>
        )}

        {/* Zone principale : George Index + répartition sectorielle */}
        <div className="flex flex-wrap gap-4 pb-3.5" style={{ borderBottom: "1px solid var(--hairline)" }}>
          <section aria-label="George Index par panier" className="gd-panel" style={{ flex: "999 1 520px" }}>
            <h2 className="gd-label">George Index par panier</h2>
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
            <div className="grid gap-x-6 gap-y-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 240px), 1fr))" }}>
              {baskets.map((b) => (
                <BasketIndexRow key={b.id} basketId={b.id} basketName={b.name} />
              ))}
            </div>
          </section>
          <section aria-label="Répartition de l'univers par secteur" className="gd-panel" style={{ flex: "1 1 340px" }}>
            <h2 className="gd-label">Répartition de l'univers par secteur</h2>
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
          </section>
        </div>

        {/* Décisions */}
        <section aria-label="Décisions récentes" className="gd-panel">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="gd-label">Décisions récentes</h2>
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span style={{ color: "var(--text-dim)" }}>Décision</span>
              {["Toutes", ...DECISION_TYPES].map((t) => (
                <button
                  key={t}
                  onClick={() => setDecisionTypeFilter(t)}
                  className="px-2.5 py-1 rounded-full border"
                  style={{
                    background: decisionTypeFilter === t ? "var(--accent)" : "transparent",
                    borderColor: decisionTypeFilter === t ? "var(--accent)" : "var(--hairline)",
                    color: decisionTypeFilter === t ? "#fff" : "var(--text-dim)",
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5">
              <span style={{ color: "var(--text-dim)" }}>Confiance ≥</span>
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
              <input
                type="number"
                min={0}
                max={100}
                value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value) || 0)}
                className="w-16 px-2 py-1 rounded-lg border"
                style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text)" }}
              />
              <span style={{ color: "var(--text-dim)" }}>%</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span style={{ color: "var(--text-dim)" }}>Statut</span>
              {["Toutes", ...DECISION_STATUSES].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className="px-2.5 py-1 rounded-full border"
                  style={{
                    background: statusFilter === s ? "var(--accent)" : "transparent",
                    borderColor: statusFilter === s ? "var(--accent)" : "var(--hairline)",
                    color: statusFilter === s ? "#fff" : "var(--text-dim)",
                  }}
                >
                  {s === "Toutes" ? "Toutes" : STATUS_LABELS[s]}
                </button>
              ))}
            </div>
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
                    {DECISION_COLUMNS.slice(0, 7).map((c) => (
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
                    <th className="text-left px-3 py-2 font-normal border-b" style={{ borderColor: "var(--hairline)" }}>
                      Portefeuille
                    </th>
                    {DECISION_COLUMNS.slice(7).map((c) => (
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
                    <tr
                      key={d.id}
                      onClick={() => openDecisionPopup(d)}
                      className="cursor-pointer"
                      style={{ background: i % 2 === 0 ? "var(--bg)" : "var(--panel)" }}
                    >
                      <td className="px-3 py-2 font-bold">{d.symbol}</td>
                      <td className="px-3 py-2">
                        <span className={decisionTagClass(d.decision_type)}>{d.decision_type}</span>
                      </td>
                      <td className="px-3 py-2" style={{ color: "var(--text-dim)" }}>
                        {STATUS_LABELS[d.status] ?? d.status}
                      </td>
                      <td className="px-3 py-2">{d.entry_price.toFixed(2)} €</td>
                      <td className="px-3 py-2">{d.take_profit != null ? `${d.take_profit.toFixed(2)} €` : "—"}</td>
                      <td className="px-3 py-2">{d.stop_loss != null ? `${d.stop_loss.toFixed(2)} €` : "—"}</td>
                      <td className="px-3 py-2 font-bold" style={{ color: scoreColor(d.confidence) }}>
                        {Math.round(d.confidence)}%
                      </td>
                      <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={checkedIds.has(d.id)}
                          onChange={() => toggleChecked(d.id)}
                          className="w-3.5 h-3.5 cursor-pointer"
                        />
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

        </section>

        <div className="text-xs" style={{ color: "var(--text-dim)" }}>
          Données réelles issues de l'API — la plupart des décisions ci-dessus viennent de figures chartistes réellement
          détectées (<code>engine.propose_decisions</code>, Phase 6) ; quelques-unes plus anciennes restent un jeu de
          démonstration illustratif (<code>ingestion/seed_demo.py</code>).
        </div>
      </div>
    </div>
  );
}
