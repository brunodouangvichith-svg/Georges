import { useEffect, useMemo, useState } from "react";
import BondHistoryChart from "../components/BondHistoryChart";
import ResponsePopup from "../components/ResponsePopup";
import {
  useBondAlertEvents,
  useBondBulletin,
  useBondCollectionRuns,
  useBondDashboard,
  useBondHistory,
  useBondThresholds,
  useRefreshBonds,
  useUpdateBondThreshold,
} from "../api/queries";

// Onglet "Obligataire" — Obligataire Watch (api/routers/bonds.py), dans le
// thème habituel de George (bleu nuit, blanc, vert/rouge). Convention de
// couleur des variations, rappelée à l'écran : une HAUSSE de taux est en
// rouge (financement plus cher, prix des obligations en baisse), une BAISSE
// en vert. Aucune valeur fabriquée : un instrument jamais collecté affiche
// "donnée indisponible".

const INSTRUMENTS = {
  OAT_FR_10Y: { label: "OAT France 10 ans", short: "OAT 10a", color: "var(--accent)", width: 2.4 },
  BUND_DE_10Y: { label: "Bund Allemagne 10 ans", short: "Bund 10a", color: "var(--text)", width: 1.6 },
  UST_US_10Y: { label: "Treasury US 10 ans", short: "UST 10a", color: "var(--warning)", width: 1.6 },
  UST_US_2Y: { label: "Treasury US 2 ans", short: "UST 2a", color: "var(--text-dim)", width: 1.4, dash: "5 3" },
  SPREAD_OAT_BUND_BPS: { label: "Spread OAT-Bund", short: "Spread", unit: "pb" },
};
const HISTORY_INSTRUMENTS = ["OAT_FR_10Y", "BUND_DE_10Y", "UST_US_10Y", "UST_US_2Y"];
const RANGES = [
  { key: "1a", label: "1 an", days: 365 },
  { key: "3a", label: "3 ans", days: 3 * 365 },
  { key: "5a", label: "5 ans", days: 5 * 365 },
];
const DIRECTION_LABEL = { above: "au-dessus de", below: "en dessous de" };
const RUN_STATUS = {
  success: { label: "Réussie", color: "var(--positive)" },
  partial: { label: "Partielle", color: "var(--warning)" },
  failed: { label: "Échec", color: "var(--negative)" },
  running: { label: "En cours", color: "var(--text-dim)" },
};

const labelOf = (code) => INSTRUMENTS[code]?.label ?? code;
const unitOf = (code) => INSTRUMENTS[code]?.unit ?? "%";
const dateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

function Panel({ title, children, className = "", right }) {
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

// Variation en points de base : ▲ rouge = hausse de taux, ▼ vert = baisse.
function Variation({ label, bps }) {
  if (bps == null) {
    return (
      <span className="mono" style={{ color: "var(--text-dim)" }}>
        {label} n/d
      </span>
    );
  }
  const up = bps > 0;
  const flat = bps === 0;
  return (
    <span className="mono" style={{ color: flat ? "var(--text-dim)" : up ? "var(--negative)" : "var(--positive)" }}>
      {label} <span aria-hidden="true">{flat ? "=" : up ? "▲" : "▼"}</span>
      <span className="sr-only">{flat ? "stable" : up ? "hausse" : "baisse"}</span>
      {` ${Math.abs(bps).toFixed(0)} pb`}
    </span>
  );
}

function YieldCard({ card }) {
  const meta = INSTRUMENTS[card.instrument] ?? { label: card.instrument };
  return (
    <div className="border rounded-[10px] p-3 flex flex-col gap-1.5 min-w-0" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        <span aria-hidden="true" className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: meta.color ?? "var(--text-dim)" }} />
        {meta.label}
      </div>
      {card.value_pct == null ? (
        <div className="text-[13px]" style={{ color: "var(--text-dim)" }}>
          Donnée indisponible (aucune collecte réussie)
        </div>
      ) : (
        <>
          <div className="mono font-semibold text-[24px]">{card.value_pct.toFixed(2)} %</div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px]">
            <Variation label="24h" bps={card.variations_bps?.["24h"]} />
            <Variation label="7j" bps={card.variations_bps?.["7j"]} />
            <Variation label="30j" bps={card.variations_bps?.["30j"]} />
          </div>
          <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            Observé le {card.observed_at} ·{" "}
            {card.source_url ? (
              <a href={card.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
                {card.source_name}
              </a>
            ) : (
              card.source_name
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SpreadCard({ title, value, hint }) {
  return (
    <div className="border rounded-[10px] p-3 flex flex-col gap-1.5 min-w-0" style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)" }}>
      <div className="text-[11px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        {title}
      </div>
      <div className="mono font-semibold text-[24px]">{value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(0)} pb`}</div>
      <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
        {value == null ? "Données non contemporaines ou indisponibles" : hint}
      </div>
    </div>
  );
}

// Une ligne de seuil, modifiable en place. L'état local repart de la valeur
// serveur à chaque mise à jour réussie (updated_at change).
function ThresholdRow({ threshold, mutation }) {
  const [value, setValue] = useState(String(threshold.threshold_pct));
  const [enabled, setEnabled] = useState(threshold.enabled);
  const [error, setError] = useState(null);

  useEffect(() => {
    setValue(String(threshold.threshold_pct));
    setEnabled(threshold.enabled);
  }, [threshold.threshold_pct, threshold.enabled, threshold.updated_at]);

  const parsed = Number(value.replace(",", "."));
  const valid = value.trim() !== "" && Number.isFinite(parsed);
  const dirty = (valid && parsed !== threshold.threshold_pct) || enabled !== threshold.enabled;
  const inputId = `threshold-${threshold.id}`;
  const saving = mutation.isPending && mutation.variables?.id === threshold.id;

  function save() {
    setError(null);
    mutation.mutate(
      {
        id: threshold.id,
        thresholdPct: valid && parsed !== threshold.threshold_pct ? parsed : undefined,
        enabled: enabled !== threshold.enabled ? enabled : undefined,
      },
      { onError: (err) => setError(err.message) }
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2 border-b" style={{ borderColor: "var(--hairline)" }}>
      <label htmlFor={inputId} className="text-[12.5px] flex-1" style={{ minWidth: 200 }}>
        <b>{labelOf(threshold.instrument)}</b>{" "}
        <span style={{ color: "var(--text-dim)" }}>alerte {DIRECTION_LABEL[threshold.direction] ?? threshold.direction}</span>
      </label>
      <div className="flex items-center gap-1.5">
        <input
          id={inputId}
          type="text"
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={!valid}
          className="mono text-[13px] rounded-md px-2 border text-right"
          style={{ width: 86, minHeight: 34, background: "var(--panel-alt)", borderColor: valid ? "var(--hairline)" : "var(--negative)", color: "var(--text)" }}
        />
        <span className="text-[12px]" style={{ color: "var(--text-dim)" }}>
          {unitOf(threshold.instrument)}
        </span>
      </div>
      <label className="flex items-center gap-1.5 text-[12px] cursor-pointer">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Active
      </label>
      <button
        onClick={save}
        disabled={!dirty || !valid || saving}
        className="text-[12px] font-semibold rounded-lg px-3"
        style={{
          minHeight: 34,
          background: dirty && valid ? "var(--accent)" : "var(--panel-alt)",
          color: dirty && valid ? "#fff" : "var(--text-dim)",
          cursor: dirty && valid && !saving ? "pointer" : "default",
        }}
      >
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
      {error && (
        <div role="alert" className="w-full text-[11.5px]" style={{ color: "var(--negative)" }}>
          {error}
        </div>
      )}
    </div>
  );
}

export default function Obligataire() {
  const [range, setRange] = useState("1a");
  const [popup, setPopup] = useState(null);

  const { data: dashboard, isLoading: dashboardLoading, isError: dashboardError } = useBondDashboard();
  const oat = useBondHistory("OAT_FR_10Y");
  const bund = useBondHistory("BUND_DE_10Y");
  const ust10 = useBondHistory("UST_US_10Y");
  const ust2 = useBondHistory("UST_US_2Y");
  const { data: thresholds } = useBondThresholds();
  const { data: activeAlerts } = useBondAlertEvents({ status: "triggered", limit: 20 });
  const { data: alertHistory } = useBondAlertEvents({ limit: 15 });
  const { data: runs } = useBondCollectionRuns({ limit: 8 });
  const { data: bulletin, isLoading: bulletinLoading } = useBondBulletin();
  const updateThreshold = useUpdateBondThreshold();
  const refreshBonds = useRefreshBonds();

  const historyLoading = oat.isLoading || bund.isLoading || ust10.isLoading || ust2.isLoading;
  const series = useMemo(() => {
    const histories = { OAT_FR_10Y: oat.data, BUND_DE_10Y: bund.data, UST_US_10Y: ust10.data, UST_US_2Y: ust2.data };
    return HISTORY_INSTRUMENTS.map((code) => ({ key: code, ...INSTRUMENTS[code], points: histories[code] ?? [] }));
  }, [oat.data, bund.data, ust10.data, ust2.data]);
  const rangeDays = RANGES.find((r) => r.key === range)?.days ?? 365;
  const lastRun = runs?.[0] ?? null;

  function refresh() {
    setPopup({ title: "Collecte obligataire", status: "loading", text: null, loadingText: "Interrogation de FRED en cours (4 séries)…" });
    refreshBonds.mutate(undefined, {
      onSuccess: (data) => {
        const failed = data.instruments_failed.length ? ` Échecs : ${data.instruments_failed.map(labelOf).join(", ")}.` : "";
        setPopup({
          title: "Collecte obligataire",
          status: "done",
          text: `${data.instruments_updated.length} série(s) mise(s) à jour, ${data.alerts_created} nouvelle(s) alerte(s).${failed}`,
        });
      },
      onError: (err) => setPopup({ title: "Collecte obligataire", status: "error", text: err.message }),
    });
  }

  return (
    <>
      <ResponsePopup popup={popup} onClose={() => setPopup(null)} />
      <div className="h-full overflow-y-auto gd-scrollbar">
        <div className="mx-auto flex flex-col gap-4 px-5 py-4" style={{ maxWidth: 1440 }}>
          {/* En-tête */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="display m-0 text-[18px] font-semibold">Obligataire Watch</h1>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                Rendements souverains, spreads et alertes ·{" "}
                {lastRun
                  ? `dernière collecte ${dateTime(lastRun.finished_at ?? lastRun.started_at)} (${RUN_STATUS[lastRun.status]?.label ?? lastRun.status})`
                  : "aucune collecte enregistrée"}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                <span style={{ color: "var(--negative)" }}>▲ hausse</span> /{" "}
                <span style={{ color: "var(--positive)" }}>▼ baisse</span> des taux
              </span>
              <button
                onClick={refresh}
                disabled={refreshBonds.isPending}
                className="text-[12.5px] font-semibold rounded-lg px-3.5"
                style={{ minHeight: 38, background: "var(--accent)", color: "#fff" }}
              >
                {refreshBonds.isPending ? "Collecte…" : "Mettre à jour les taux"}
              </button>
            </div>
          </div>

          {dashboardError && (
            <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
              Impossible de contacter l'API — le serveur met parfois 1 à 2 minutes à se réveiller, réessaie dans un instant.
            </div>
          )}

          {/* Cartes */}
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))" }}>
            {dashboardLoading &&
              HISTORY_INSTRUMENTS.map((code) => (
                <div key={code} className="border rounded-[10px] p-3 text-[12px]" style={{ borderColor: "var(--hairline)", background: "var(--panel)", color: "var(--text-dim)", minHeight: 110 }}>
                  {labelOf(code)} — chargement…
                </div>
              ))}
            {(dashboard?.cards ?? []).map((card) => (
              <YieldCard key={card.instrument} card={card} />
            ))}
            {dashboard && (
              <>
                <SpreadCard title="Spread OAT-Bund" value={dashboard.spread_oat_bund_bps} hint="Prime de risque France vs Allemagne" />
                <SpreadCard title="Pente US 10a-2a" value={dashboard.us_curve_slope_bps} hint="Négative = courbe inversée" />
              </>
            )}
          </div>

          {/* Historique + bulletin */}
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 420px), 1fr))" }}>
            <Panel
              title="Historique des rendements"
              right={
                <div role="group" aria-label="Période" className="flex gap-1">
                  {RANGES.map((r) => (
                    <button
                      key={r.key}
                      aria-pressed={range === r.key}
                      onClick={() => setRange(r.key)}
                      className="text-[11.5px] px-3 rounded-full border"
                      style={{
                        minHeight: 30,
                        background: range === r.key ? "var(--accent)" : "transparent",
                        borderColor: range === r.key ? "var(--accent)" : "var(--hairline)",
                        color: range === r.key ? "#fff" : "var(--text-dim)",
                      }}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              }
            >
              {historyLoading ? (
                <div className="text-[12px]" style={{ color: "var(--text-dim)", minHeight: 240 }}>
                  Chargement de l'historique…
                </div>
              ) : (
                <BondHistoryChart series={series} rangeDays={rangeDays} />
              )}
              <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                OAT et Bund : séries mensuelles (OCDE via FRED) · Treasuries : quotidiennes.
              </div>
            </Panel>

            <Panel title="Bulletin du jour">
              {bulletinLoading ? (
                <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                  Préparation du bulletin…
                </div>
              ) : bulletin?.bulletin ? (
                <div className="text-[12.5px] leading-relaxed whitespace-pre-wrap overflow-y-auto gd-scrollbar pr-1" style={{ maxHeight: 420 }}>
                  {bulletin.bulletin}
                </div>
              ) : (
                <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                  Bulletin indisponible.
                </div>
              )}
            </Panel>
          </div>

          {/* Alertes, seuils, collecte */}
          <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))" }}>
            <Panel title="Seuils d'alerte" className="lg:col-span-2">
              {(thresholds ?? []).length === 0 ? (
                <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucun seuil configuré (le job quotidien les crée au premier passage).
                </div>
              ) : (
                <div>
                  {thresholds.map((t) => (
                    <ThresholdRow key={t.id} threshold={t} mutation={updateThreshold} />
                  ))}
                  <div className="text-[11px] mt-2" style={{ color: "var(--text-dim)" }}>
                    Valeurs indicatives, pas des recommandations. Le spread s'exprime en points de base, les taux en %.
                  </div>
                </div>
              )}
            </Panel>

            <Panel title={`Alertes actives (${activeAlerts?.length ?? 0})`}>
              {(activeAlerts ?? []).length === 0 ? (
                <div className="text-[12.5px]" style={{ color: "var(--positive)" }}>
                  Aucun seuil franchi actuellement.
                </div>
              ) : (
                activeAlerts.map((e) => (
                  <div key={e.id} className="rounded-md px-2.5 py-2 text-[12.5px]" style={{ background: "var(--panel-alt)", borderLeft: "3px solid var(--negative)" }}>
                    <div>{e.message}</div>
                    <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>
                      Depuis le {dateTime(e.triggered_at)}
                    </div>
                  </div>
                ))
              )}
            </Panel>

            <Panel title="Historique des alertes" className="lg:col-span-2">
              {(alertHistory ?? []).length === 0 ? (
                <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucune alerte enregistrée.
                </div>
              ) : (
                alertHistory.map((e) => (
                  <div key={e.id} className="flex items-start gap-2 text-[12px] py-1 border-b" style={{ borderColor: "var(--hairline)" }}>
                    <span
                      className="text-[10.5px] font-semibold px-1.5 py-0.5 rounded flex-shrink-0"
                      style={{
                        color: e.status === "triggered" ? "var(--negative)" : "var(--positive)",
                        background: `color-mix(in srgb, ${e.status === "triggered" ? "var(--negative)" : "var(--positive)"} 15%, transparent)`,
                      }}
                    >
                      {e.status === "triggered" ? "Déclenchée" : "Levée"}
                    </span>
                    <span className="flex-1 min-w-0">{e.message}</span>
                    <span className="mono text-[11px] flex-shrink-0" style={{ color: "var(--text-dim)" }}>
                      {new Date(e.triggered_at).toLocaleDateString("fr-FR")}
                    </span>
                  </div>
                ))
              )}
            </Panel>

            <Panel title="Collecte">
              {(runs ?? []).length === 0 ? (
                <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucune collecte enregistrée.
                </div>
              ) : (
                runs.map((r) => (
                  <div key={r.id} className="text-[12px] py-1 border-b" style={{ borderColor: "var(--hairline)" }}>
                    <div className="flex justify-between gap-2">
                      <span className="mono">{dateTime(r.started_at)}</span>
                      <span className="font-semibold" style={{ color: RUN_STATUS[r.status]?.color ?? "var(--text-dim)" }}>
                        {RUN_STATUS[r.status]?.label ?? r.status} · {r.instruments_succeeded}/{r.instruments_requested}
                      </span>
                    </div>
                    {r.error_summary && (
                      <div className="text-[11px] mt-0.5" style={{ color: "var(--negative)" }}>
                        {r.error_summary}
                      </div>
                    )}
                  </div>
                ))
              )}
            </Panel>
          </div>
        </div>
      </div>
    </>
  );
}
