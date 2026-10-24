import { useState } from "react";
import ResponsePopup from "../components/ResponsePopup";
import { decisionColor, decisionTagClass } from "../data";
import {
  useConfirmDecision,
  useConfirmExit,
  useDecisions,
  useExplainDecision,
  useMonitorDecisions,
  usePerformance,
  useProposeDecisions,
  useProposeLevels,
} from "../api/queries";

// Onglet "Trading" — suivi du cycle de vie des décisions de George
// (api/routers/decisions.py), dans le thème George. Quatre colonnes, une par
// statut. George ne passe AUCUN ordre : "confirmer" enregistre seulement la
// décision comme position suivie, "confirmer la sortie" la clôture et écrit
// son résultat dans decision_outcomes. La performance réalisée vient de
// GET /decisions/performance (engine/performance.py) : seules les décisions
// clôturées comptent, jamais les rendements latents des positions ouvertes.

const COLUMNS = [
  { status: "proposee", title: "Proposées", hint: "À valider ou ajuster" },
  { status: "confirmee", title: "En position", hint: "Suivies par le job de surveillance" },
  { status: "sortie_proposee", title: "Sortie proposée", hint: "Take-profit ou stop-loss franchi" },
  { status: "cloturee", title: "Clôturées", hint: "Historique" },
];

const EXIT_LABELS = { sortie_totale: "Sortie totale", sortie_partielle: "Sortie partielle" };

const RESULT_LABELS = { take_profit_hit: "Take-profit touché", stop_loss_hit: "Stop-loss touché" };

// Pourcentage signé, en vert si positif, rouge si négatif.
function Pct({ value, className = "" }) {
  if (value == null) return <span className={`mono ${className}`} style={{ color: "var(--text-dim)" }}>—</span>;
  const color = value > 0 ? "var(--positive)" : value < 0 ? "var(--negative)" : "var(--text-dim)";
  return (
    <span className={`mono ${className}`} style={{ color }}>
      {`${value > 0 ? "+" : ""}${value.toFixed(2)} %`}
    </span>
  );
}

const money = (v) => (v == null ? "—" : `${Number(v).toFixed(2)} €`);
const day = (iso) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—");
const parseLevel = (text) => {
  if (text.trim() === "") return null;
  const n = Number(text.replace(",", "."));
  return Number.isFinite(n) && n > 0 ? n : NaN;
};

function Level({ label, value, color }) {
  return (
    <div className="flex-1 min-w-0 rounded-md px-2 py-1.5" style={{ background: "var(--panel-alt)" }}>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="mono text-[12.5px] font-semibold" style={{ color: color ?? "var(--text)" }}>
        {money(value)}
      </div>
    </div>
  );
}

function LevelInput({ id, label, value, onChange, invalid }) {
  return (
    <div className="flex-1 min-w-0">
      <label htmlFor={id} className="block text-[10px] uppercase tracking-wider mb-0.5" style={{ color: "var(--text-dim)" }}>
        {label}
      </label>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid}
        className="mono w-full text-[12.5px] rounded-md px-2 border"
        style={{ minHeight: 32, background: "var(--panel-alt)", borderColor: invalid ? "var(--negative)" : "var(--hairline)", color: "var(--text)" }}
      />
    </div>
  );
}

function ProposedActions({ decision, confirmMutation, levelsMutation }) {
  const [tp, setTp] = useState(decision.take_profit != null ? String(decision.take_profit) : "");
  const [sl, setSl] = useState(decision.stop_loss != null ? String(decision.stop_loss) : "");
  const [error, setError] = useState(null);
  const tpValue = parseLevel(tp);
  const slValue = parseLevel(sl);
  const invalid = Number.isNaN(tpValue) || Number.isNaN(slValue);
  const busy =
    (confirmMutation.isPending && confirmMutation.variables?.id === decision.id) ||
    (levelsMutation.isPending && levelsMutation.variables === decision.id);

  function confirm() {
    setError(null);
    confirmMutation.mutate(
      {
        id: decision.id,
        takeProfit: tpValue != null && tpValue !== decision.take_profit ? tpValue : undefined,
        stopLoss: slValue != null && slValue !== decision.stop_loss ? slValue : undefined,
      },
      { onError: (err) => setError(err.message) }
    );
  }

  function recompute() {
    setError(null);
    levelsMutation.mutate(decision.id, {
      onSuccess: (updated) => {
        setTp(updated.take_profit != null ? String(updated.take_profit) : "");
        setSl(updated.stop_loss != null ? String(updated.stop_loss) : "");
      },
      onError: (err) => setError(err.message),
    });
  }

  return (
    <>
      <div className="flex gap-2">
        <LevelInput id={`tp-${decision.id}`} label="Take-profit (€)" value={tp} onChange={setTp} invalid={Number.isNaN(tpValue)} />
        <LevelInput id={`sl-${decision.id}`} label="Stop-loss (€)" value={sl} onChange={setSl} invalid={Number.isNaN(slValue)} />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button className="gd-btn gd-btn--solid" style={{ flex: "1 1 120px" }} onClick={confirm} disabled={busy || invalid}>
          Confirmer
        </button>
        {decision.pattern_id != null && (
          <button className="gd-btn" style={{ flex: "1 1 120px" }} onClick={recompute} disabled={busy}>
            Recalculer
          </button>
        )}
      </div>
      {error && (
        <div role="alert" className="text-[11.5px]" style={{ color: "var(--negative)" }}>
          {error}
        </div>
      )}
    </>
  );
}

function ExitActions({ decision, exitMutation }) {
  const [armed, setArmed] = useState(false);
  const [error, setError] = useState(null);
  const busy = exitMutation.isPending && exitMutation.variables === decision.id;

  return (
    <>
      <div className="rounded-md px-2.5 py-2 text-[12px]" style={{ background: "var(--panel-alt)", borderLeft: "3px solid var(--warning)" }}>
        <div className="font-semibold">
          {EXIT_LABELS[decision.exit_scenario] ?? decision.exit_scenario ?? "Sortie"}
          {decision.exit_volume_confirmed != null && (
            <span className="font-normal" style={{ color: "var(--text-dim)" }}>
              {decision.exit_volume_confirmed ? " · confirmée par le volume" : " · volume non confirmé"}
            </span>
          )}
        </div>
        {decision.exit_justification && (
          <div className="mt-1 leading-relaxed" style={{ color: "var(--text-dim)" }}>
            {decision.exit_justification}
          </div>
        )}
      </div>
      {armed ? (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-[11.5px] w-full" style={{ color: "var(--text-dim)" }}>
            Clôturer définitivement {decision.symbol} ?
          </span>
          <button
            className="gd-btn"
            style={{ flex: "1 1 100px", background: "var(--negative)", borderColor: "var(--negative)", color: "#fff" }}
            disabled={busy}
            onClick={() => {
              setError(null);
              exitMutation.mutate(decision.id, { onError: (err) => setError(err.message), onSettled: () => setArmed(false) });
            }}
          >
            {busy ? "Clôture…" : "Oui, clôturer"}
          </button>
          <button className="gd-btn" style={{ flex: "1 1 100px" }} onClick={() => setArmed(false)} disabled={busy}>
            Annuler
          </button>
        </div>
      ) : (
        <button className="gd-btn gd-btn--solid" onClick={() => setArmed(true)}>
          Confirmer la sortie
        </button>
      )}
      {error && (
        <div role="alert" className="text-[11.5px]" style={{ color: "var(--negative)" }}>
          {error}
        </div>
      )}
    </>
  );
}

function DecisionCard({ decision, onExplain, mutations, outcome }) {
  return (
    <article
      aria-label={`${decision.symbol} — ${decision.decision_type}`}
      className="rounded-lg border p-3 flex flex-col gap-2"
      style={{ borderColor: "var(--hairline)", background: "var(--panel)", borderLeft: `3px solid ${decisionColor(decision.decision_type)}` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="mono font-semibold text-[13.5px]">{decision.symbol}</div>
          <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            Créée le {day(decision.created_at)} · confiance {Math.round(decision.confidence)} %
          </div>
        </div>
        <span className={decisionTagClass(decision.decision_type)}>{decision.decision_type}</span>
      </div>

      {decision.status === "proposee" ? (
        <>
          <Level label="Entrée" value={decision.entry_price} />
          <ProposedActions decision={decision} confirmMutation={mutations.confirm} levelsMutation={mutations.levels} />
        </>
      ) : (
        <div className="flex gap-1.5">
          <Level label="Entrée" value={decision.entry_price} />
          <Level label="Take-profit" value={decision.take_profit} color="var(--positive)" />
          <Level label="Stop-loss" value={decision.stop_loss} color="var(--negative)" />
        </div>
      )}

      {decision.status === "sortie_proposee" && <ExitActions decision={decision} exitMutation={mutations.exit} />}

      {decision.status === "cloturee" && (
        <div className="flex items-center justify-between gap-2 rounded-md px-2.5 py-2" style={{ background: "var(--panel-alt)" }}>
          <div className="text-[11.5px] min-w-0" style={{ color: "var(--text-dim)" }}>
            {outcome ? RESULT_LABELS[outcome.result] ?? outcome.result : EXIT_LABELS[decision.exit_scenario] ?? "Clôturée"}
            {outcome ? ` · le ${day(outcome.closed_at)}` : ""}
          </div>
          {outcome ? (
            <Pct value={outcome.pnl_pct} className="text-[15px] font-semibold" />
          ) : (
            <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
              Résultat non disponible
            </span>
          )}
        </div>
      )}

      {decision.rationale && (
        <p className="m-0 text-[12px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
          {decision.rationale}
        </p>
      )}
      <button className="gd-btn self-start" style={{ minHeight: 30, fontSize: 11.5 }} onClick={() => onExplain(decision)}>
        George explique →
      </button>
    </article>
  );
}

function Column({ column, query, onExplain, mutations, outcomes }) {
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? items.length;
  return (
    <section aria-label={column.title} className="gd-panel" style={{ background: "transparent" }}>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="display m-0 text-[14px] font-semibold">
          {column.title} <span className="mono text-[12px]" style={{ color: "var(--text-dim)" }}>({total})</span>
        </h2>
        <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          {column.hint}
        </span>
      </div>
      {query.isLoading && (
        <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
          Chargement…
        </div>
      )}
      {query.isError && (
        <div className="text-[12px]" style={{ color: "var(--negative)" }}>
          Impossible de charger cette colonne.
        </div>
      )}
      {!query.isLoading && !query.isError && items.length === 0 && (
        <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
          Aucune décision.
        </div>
      )}
      <div className="flex flex-col gap-2.5 overflow-y-auto gd-scrollbar pr-0.5" style={{ maxHeight: "70vh" }}>
        {items.map((d) => (
          <DecisionCard key={d.id} decision={d} onExplain={onExplain} mutations={mutations} outcome={outcomes?.[d.id]} />
        ))}
      </div>
      {total > items.length && (
        <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          {items.length} affichées sur {total} (les plus récentes).
        </div>
      )}
    </section>
  );
}

function Stat({ label, children, hint }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0" style={{ flex: "1 1 130px" }}>
      <div className="text-[10.5px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="text-[18px] font-semibold">{children}</div>
      {hint && (
        <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}

// Bandeau de performance réalisée + détail par type de figure.
function PerformancePanel({ query }) {
  const summary = query.data?.summary;
  const patterns = query.data?.by_pattern ?? [];
  return (
    <section aria-label="Performance réalisée" className="gd-panel">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="display m-0 text-[14px] font-semibold">Performance réalisée</h2>
        <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          Positions clôturées uniquement · % bruts, sans frais ni taille de position · total = somme des %
        </span>
      </div>
      {query.isLoading && (
        <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
          Chargement…
        </div>
      )}
      {query.isError && (
        <div className="text-[12px]" style={{ color: "var(--negative)" }}>
          Performance indisponible — l'API n'expose peut-être pas encore cette route (redéploiement Render nécessaire).
        </div>
      )}
      {summary && summary.count === 0 && (
        <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
          Aucune position clôturée pour l'instant : la performance apparaîtra après la première sortie confirmée.
        </div>
      )}
      {summary && summary.count > 0 && (
        <>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            <Stat label="Positions clôturées">{summary.count}</Stat>
            <Stat label="Taux de réussite" hint={`${summary.wins} gagnante(s), ${summary.losses} perdante(s)`}>
              <span className="mono">{summary.win_rate_pct != null ? `${summary.win_rate_pct.toFixed(0)} %` : "—"}</span>
            </Stat>
            <Stat label="Gain moyen">
              <Pct value={summary.avg_gain_pct} />
            </Stat>
            <Stat label="Perte moyenne">
              <Pct value={summary.avg_loss_pct} />
            </Stat>
            <Stat label="Moyenne par trade">
              <Pct value={summary.avg_pnl_pct} />
            </Stat>
            <Stat label="Total" hint="somme des %">
              <Pct value={summary.total_pnl_pct} />
            </Stat>
          </div>
          {summary.count < 10 && (
            <div className="text-[11.5px]" style={{ color: "var(--warning)" }}>
              Encore peu de positions clôturées ({summary.count}) : ces chiffres ne sont pas significatifs.
            </div>
          )}
          {patterns.length > 0 && (
            <div className="overflow-x-auto gd-scrollbar">
              <table className="w-full border-collapse text-[12px]" style={{ minWidth: 520 }}>
                <caption className="sr-only">Performance par type de figure</caption>
                <thead>
                  <tr>
                    {["Figure", "Trades", "Réussite", "Moyenne", "Total"].map((h, i) => (
                      <th
                        key={h}
                        scope="col"
                        className="text-[10.5px] uppercase tracking-wider font-medium py-1.5 px-2"
                        style={{ color: "var(--text-dim)", borderBottom: "1px solid var(--hairline)", textAlign: i === 0 ? "left" : "right" }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {patterns.map((p) => (
                    <tr key={p.pattern_type}>
                      <td className="py-1.5 px-2" style={{ borderBottom: "1px solid var(--hairline)" }}>
                        {p.pattern_type}
                      </td>
                      <td className="mono py-1.5 px-2 text-right" style={{ borderBottom: "1px solid var(--hairline)" }}>
                        {p.count}
                      </td>
                      <td className="mono py-1.5 px-2 text-right" style={{ borderBottom: "1px solid var(--hairline)" }}>
                        {p.win_rate_pct != null ? `${p.win_rate_pct.toFixed(0)} %` : "—"}
                      </td>
                      <td className="py-1.5 px-2 text-right" style={{ borderBottom: "1px solid var(--hairline)" }}>
                        <Pct value={p.avg_pnl_pct} />
                      </td>
                      <td className="py-1.5 px-2 text-right" style={{ borderBottom: "1px solid var(--hairline)" }}>
                        <Pct value={p.total_pnl_pct} />
                      </td>
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

export default function Trading() {
  const [popup, setPopup] = useState(null);
  const queries = {
    proposee: useDecisions({ status: "proposee", limit: 200 }),
    confirmee: useDecisions({ status: "confirmee", limit: 200 }),
    sortie_proposee: useDecisions({ status: "sortie_proposee", limit: 200 }),
    cloturee: useDecisions({ status: "cloturee", limit: 200 }),
  };
  const mutations = {
    confirm: useConfirmDecision(),
    levels: useProposeLevels(),
    exit: useConfirmExit(),
  };
  const explain = useExplainDecision();
  const performance = usePerformance();
  const outcomes = Object.fromEntries((performance.data?.trades ?? []).map((t) => [t.decision_id, t]));
  const propose = useProposeDecisions();
  const monitor = useMonitorDecisions();

  function runJob(mutation, title, loadingText, summary) {
    setPopup({ title, status: "loading", text: null, loadingText });
    mutation.mutate(undefined, {
      onSuccess: (created) => setPopup({ title, status: "done", text: summary(created.length) }),
      onError: (err) => setPopup({ title, status: "error", text: err.message }),
    });
  }

  function onExplain(decision) {
    const title = `George explique — ${decision.symbol}`;
    setPopup({ title, status: "loading", text: null });
    explain.mutate(
      { decisionId: decision.id },
      {
        onSuccess: (data) => setPopup({ title, status: "done", text: data.explanation }),
        onError: (err) => setPopup({ title, status: "error", text: err.message }),
      }
    );
  }

  return (
    <>
      <ResponsePopup popup={popup} onClose={() => setPopup(null)} />
      <div className="h-full overflow-y-auto gd-scrollbar">
        <div className="mx-auto flex flex-col gap-4 px-5 py-4" style={{ maxWidth: 1600 }}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="display m-0 text-[18px] font-semibold">Trading</h1>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                Cycle de vie des décisions de George. Aucun ordre n'est passé : confirmer enregistre une position suivie.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className="gd-btn"
                disabled={propose.isPending}
                onClick={() =>
                  runJob(propose, "Détection d'opportunités", "Analyse des figures actives…", (n) =>
                    n === 0 ? "Aucune nouvelle proposition." : `${n} nouvelle(s) proposition(s).`
                  )
                }
              >
                {propose.isPending ? "Détection…" : "Lancer une détection"}
              </button>
              <button
                className="gd-btn gd-btn--solid"
                disabled={monitor.isPending}
                onClick={() =>
                  runJob(monitor, "Surveillance des positions", "Vérification des take-profit et stop-loss…", (n) =>
                    n === 0 ? "Aucun niveau franchi." : `${n} sortie(s) proposée(s).`
                  )
                }
              >
                {monitor.isPending ? "Surveillance…" : "Surveiller les positions"}
              </button>
            </div>
          </div>

          <PerformancePanel query={performance} />

          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))" }}>
            {COLUMNS.map((c) => (
              <Column
                key={c.status}
                column={c}
                query={queries[c.status]}
                onExplain={onExplain}
                mutations={mutations}
                outcomes={outcomes}
              />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
