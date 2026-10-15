import { useEffect, useMemo, useRef, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import GeorgeIndexTile from "../components/GeorgeIndexTile";
import ResponsePopup from "../components/ResponsePopup";
import UniversRadar from "../components/UniversRadar";
import WatchlistRow from "../components/WatchlistRow";
import { decisionTagClass } from "../data";
import { useVoiceCapture } from "../hooks/useVoiceCapture";
import {
  useAgentActivity,
  useBaskets,
  useChat,
  useDecisions,
  useExplainDecision,
  useLatestPatterns,
  useRefreshPrices,
  useEnergyPrices,
  useSecurities,
  useSecurityDividends,
  useSecurityFundamentals,
  useSecurityPatterns,
  useSecurityPrices,
  useTriggerCollection,
} from "../api/queries";

// Écran Univers — thème "Paper Lab" (noir et blanc, monospace, radar
// central, grille de panneaux). Le thème lui-même est porté par Layout
// (classe .theme-paperlab, voir index.css). Toutes les données affichées
// viennent de l'API : aucun chiffre de démonstration ici.

const ENERGY_LABELS = {
  BRENT_CRUDE_USD: "Brent",
  WTI_USD: "WTI",
  NATURAL_GAS_USD: "Gaz naturel",
  DIESEL_USD: "Diesel",
  HEATING_OIL_USD: "Fioul domestique",
  GASOLINE_USD: "Essence",
};
const ENERGY_ORDER = Object.keys(ENERGY_LABELS);

const FILTERS = ["Tous", "Achat", "Surveiller", "Alléger"];

const AGENT_STATUS_LABEL = { validated: "validé", pending: "en attente", quarantine: "quarantaine" };

const BULLISH = new Set(["Achat", "Renforcer"]);

function EmptyState({ children }) {
  return (
    <div className="text-[12px] p-3 border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
      {children}
    </div>
  );
}

function Panel({ title, children, className = "", style, label }) {
  return (
    <section aria-label={label ?? title} className={`pl-panel ${className}`} style={style}>
      <h2 className="pl-label">{title}</h2>
      {children}
    </section>
  );
}

function Counter({ label, value, ratio }) {
  return (
    <div className="flex flex-col gap-1.5" style={{ minWidth: 110, flex: "1 1 110px", maxWidth: 190 }}>
      <div className="pl-label" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="text-[18px] font-bold">{value}</div>
      <div style={{ height: 3, background: "var(--hairline)", position: "relative" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: `${Math.round(Math.max(0, Math.min(1, ratio)) * 100)}%`,
            background: "var(--text)",
          }}
        />
      </div>
    </div>
  );
}

const time = (iso) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });

export default function Univers() {
  const [filter, setFilter] = useState("Tous");
  const [selected, setSelected] = useState(null);
  const [dockMsg, setDockMsg] = useState(null);
  const [popup, setPopup] = useState(null); // { title, status: "listening"|"loading"|"done"|"error", text }
  const chatMutation = useChat();
  const explainMutation = useExplainDecision();
  const refreshPricesMutation = useRefreshPrices();
  // Annule le polling de useRefreshPrices (voir queries.js) si l'écran est
  // démonté avant la fin — sans ça, la boucle de polling continue en
  // arrière-plan et invalide le cache pour un écran qui n'est plus affiché.
  const refreshAbortControllerRef = useRef(null);

  useEffect(() => {
    return () => refreshAbortControllerRef.current?.abort();
  }, []);

  function refreshPrices() {
    setPopup({
      title: "Mise à jour des prix",
      status: "loading",
      text: null,
      loadingText: "Téléchargement des prix en cours (jusqu'à quelques minutes pour tout l'univers, 10 ans d'historique par titre — exécuté en tâche de fond côté serveur, cette fenêtre patiente le temps qu'il faut)…",
    });
    const controller = new AbortController();
    refreshAbortControllerRef.current = controller;
    refreshPricesMutation.mutate(controller.signal, {
      onSuccess: (data) => {
        const failedText = data.failed_symbols.length
          ? ` Échecs : ${data.failed_symbols.join(", ")}.`
          : "";
        setPopup({
          title: "Mise à jour des prix",
          status: "done",
          text: `${data.updated_count}/${data.total} titres mis à jour.${failedText}`,
        });
      },
      onError: (err) => {
        if (controller.signal.aborted) return; // écran démonté, rien à afficher
        setPopup({ title: "Mise à jour des prix", status: "error", text: err.message });
      },
    });
  }

  const triggerCollectionMutation = useTriggerCollection();

  function triggerMacroCollection() {
    setPopup({
      title: "Collecte macro",
      status: "loading",
      text: null,
      loadingText: "Interrogation de FRED et de la BCE en cours…",
    });
    triggerCollectionMutation.mutate("donnees_macro", {
      onSuccess: (data) =>
        setPopup({
          title: "Collecte macro",
          status: "done",
          text: `${data.validated.length} validée(s), ${data.quarantined_count} en quarantaine.`,
        }),
      onError: (err) => setPopup({ title: "Collecte macro", status: "error", text: err.message }),
    });
  }

  const voice = useVoiceCapture({
    onListening: () => setPopup({ title: "Commande vocale", status: "listening", text: "" }),
    onInterim: (text) => setPopup((prev) => (prev?.status === "listening" ? { ...prev, text } : prev)),
    onError: (message) => setPopup({ title: "Commande vocale", status: "error", text: message }),
    onFinal: (question) => {
      if (!question) {
        setPopup({ title: "Commande vocale", status: "error", text: "Aucune parole détectée — réessayez." });
        return;
      }
      const title = `Commande vocale — « ${question} »`;
      setPopup({ title, status: "loading", text: null });
      chatMutation.mutate(question, {
        onSuccess: (data) => setPopup({ title, status: "done", text: data.answer }),
        onError: (err) => setPopup({ title, status: "error", text: err.message }),
      });
    },
  });

  function closePopup() {
    // Coupe le micro si une écoute est en cours — sinon le navigateur
    // continue d'enregistrer alors que le popup est fermé.
    voice.abort();
    setPopup(null);
  }

  function askGeorge(question) {
    setPopup({ title: "George répond", status: "loading", text: null });
    chatMutation.mutate(question, {
      onSuccess: (data) => setPopup({ title: "George répond", status: "done", text: data.answer }),
      onError: (err) => setPopup({ title: "George répond", status: "error", text: err.message }),
    });
  }

  const { data: securitiesPage, isLoading: securitiesLoading, isError: securitiesError } = useSecurities({ limit: 200 });
  const { data: decisionsPage } = useDecisions({ limit: 200 });
  const { data: basketsPage } = useBaskets();
  const { data: agentPage } = useAgentActivity({ limit: 20 });
  const { data: energyPrices } = useEnergyPrices();

  const sortedEnergyPrices = ENERGY_ORDER.map((code) => energyPrices?.find((e) => e.commodity_code === code)).filter(
    Boolean
  );

  const securities = useMemo(() => securitiesPage?.items ?? [], [securitiesPage]);
  const symbols = useMemo(() => securities.map((s) => s.symbol), [securities]);
  const patternsBySymbol = useLatestPatterns(symbols);

  // Décisions triées par date décroissante côté API : la première rencontrée
  // par titre est donc la plus récente.
  const decisionsMap = useMemo(() => {
    const map = {};
    for (const decision of decisionsPage?.items ?? []) {
      if (!(decision.symbol in map)) map[decision.symbol] = decision;
    }
    return map;
  }, [decisionsPage]);

  const filtered =
    filter === "Tous" ? securities : securities.filter((s) => decisionsMap[s.symbol]?.decision_type === filter);

  const selectedSymbol = selected ?? securities[0]?.symbol ?? null;
  const selectedSecurity = securities.find((s) => s.symbol === selectedSymbol) ?? null;
  const selectedDecision = selectedSymbol ? decisionsMap[selectedSymbol] : null;

  const { data: selectedPatternsPage } = useSecurityPatterns(selectedSymbol, { limit: 1 });
  const {
    data: selectedPricesPage,
    isLoading: pricesLoading,
    isError: pricesError,
  } = useSecurityPrices(selectedSymbol, { limit: 250 });
  const { data: selectedFundamentals } = useSecurityFundamentals(selectedSymbol);
  const { data: selectedDividendsPage } = useSecurityDividends(selectedSymbol, { limit: 5 });

  const selectedPattern = selectedPatternsPage?.items?.[0] ?? null;
  const priceItems = useMemo(() => selectedPricesPage?.items ?? [], [selectedPricesPage]);
  const closes = useMemo(() => priceItems.map((bar) => bar.close), [priceItems]);
  // `items` ne contient que les `limit` séances les plus récentes : l'écart
  // entre `total` et leur nombre est le décalage à soustraire aux indices
  // absolus du `context` d'un pattern pour les replacer dans ce sous-ensemble.
  const indexOffset = selectedPricesPage ? selectedPricesPage.total - priceItems.length : 0;

  const georgeBaskets = (basketsPage ?? []).slice(0, 2);
  const agentEvents = useMemo(() => agentPage?.items ?? [], [agentPage]);

  // Sous-agents : dernier état connu par agent (les événements arrivent du
  // plus récent au plus ancien), avec le nombre d'événements récents.
  const agentSummary = useMemo(() => {
    const byName = new Map();
    for (const e of agentEvents) {
      const cur = byName.get(e.agent_name);
      if (cur) cur.count += 1;
      else byName.set(e.agent_name, { name: e.agent_name, status: e.status, count: 1 });
    }
    return [...byName.values()];
  }, [agentEvents]);
  const maxAgentCount = Math.max(1, ...agentSummary.map((a) => a.count));

  const decisionCounts = useMemo(() => {
    const counts = { achat: 0, surveiller: 0, alleger: 0 };
    for (const s of securities) {
      const d = decisionsMap[s.symbol]?.decision_type;
      if (!d) continue;
      if (BULLISH.has(d)) counts.achat += 1;
      else if (d === "Surveiller") counts.surveiller += 1;
      else counts.alleger += 1;
    }
    return counts;
  }, [securities, decisionsMap]);
  const activePatterns = symbols.filter((s) => patternsBySymbol?.[s]).length;
  const universeSize = Math.max(1, securities.length);

  const reasoningLines = selectedSecurity
    ? [
        `serie    = prices("${selectedSymbol}", ${priceItems.length})`,
        `figure   = detect(serie) → ${selectedPattern?.pattern_type ?? "aucune"}`,
        selectedPattern ? `conf     = ${Math.round(selectedPattern.confidence)} %` : null,
        selectedDecision
          ? `decision = ${selectedDecision.decision_type}` +
            (selectedDecision.take_profit != null ? ` · tp ${selectedDecision.take_profit.toFixed(2)}` : "") +
            (selectedDecision.stop_loss != null ? ` · sl ${selectedDecision.stop_loss.toFixed(2)}` : "")
          : "decision = —",
      ].filter(Boolean)
    : [];

  return (
    <>
      <ResponsePopup popup={popup} onClose={closePopup} onStopListening={voice.stop} />
      <div className="h-full overflow-y-auto gd-scrollbar">
        <div className="mx-auto flex flex-col gap-3.5 px-5 pt-4" style={{ maxWidth: 1440 }}>
          {/* En-tête + compteurs */}
          <header className="flex flex-wrap items-start justify-between" style={{ gap: "16px 40px" }}>
            <div className="flex flex-col gap-1" style={{ minWidth: 260 }}>
              <h1 className="m-0 text-[20px] font-bold tracking-wide">
                GEORGE / <span>Univers</span>
              </h1>
              <div className="pl-label" style={{ color: "var(--text-dim)" }}>
                CAC 40 &amp; CAC Mid 60 → décisions expliquées
              </div>
            </div>
            <div className="flex flex-wrap justify-end" style={{ gap: "14px 28px", flex: "1 1 600px" }}>
              <Counter label="Valeurs" value={securitiesLoading ? "…" : securities.length} ratio={1} />
              <Counter label="Figures actives" value={activePatterns} ratio={activePatterns / universeSize} />
              <Counter label="Achat" value={decisionCounts.achat} ratio={decisionCounts.achat / universeSize} />
              <Counter
                label="Surveiller"
                value={decisionCounts.surveiller}
                ratio={decisionCounts.surveiller / universeSize}
              />
              <Counter label="Alléger" value={decisionCounts.alleger} ratio={decisionCounts.alleger / universeSize} />
            </div>
          </header>

          {/* Barre d'actions */}
          <div
            className="flex flex-wrap items-center gap-2.5 pt-2 text-[11px]"
            style={{ borderTop: "1px solid var(--text)", color: "var(--text-dim)" }}
          >
            <span>{securitiesLoading ? "Chargement…" : `${securities.length} valeurs suivies`}</span>
            <div className="ml-auto flex flex-wrap gap-1.5">
              <button className="pl-btn" onClick={refreshPrices} disabled={refreshPricesMutation.isPending}>
                {refreshPricesMutation.isPending ? "Mise à jour…" : "Mise à jour des prix"}
              </button>
              <button className="pl-btn" onClick={triggerMacroCollection} disabled={triggerCollectionMutation.isPending}>
                {triggerCollectionMutation.isPending ? "Collecte…" : "Collecte macro"}
              </button>
            </div>
          </div>

          {securitiesError && (
            <EmptyState>
              Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
            </EmptyState>
          )}

          {/* Radar + valeur sélectionnée */}
          <div className="flex flex-wrap gap-4 pb-3.5" style={{ borderBottom: "1px solid var(--text)" }}>
            <section aria-label="Radar de l'univers" style={{ flex: "999 1 520px", minWidth: 0 }}>
              {securities.length > 0 ? (
                <UniversRadar
                  securities={securities}
                  patternsBySymbol={patternsBySymbol}
                  decisionsMap={decisionsMap}
                  selectedSymbol={selectedSymbol}
                  onSelect={setSelected}
                  closes={closes}
                />
              ) : (
                <div className="flex items-center justify-center text-[12px]" style={{ minHeight: 320, color: "var(--text-dim)" }}>
                  {securitiesLoading ? "Chargement de l'univers…" : "Le radar s'affichera dès que des titres seront en base."}
                </div>
              )}
            </section>

            <div className="flex flex-col gap-3" style={{ flex: "1 1 340px", minWidth: 0 }}>
              <section aria-label="Valeur sélectionnée" className="flex flex-col gap-2 p-3" style={{ border: "1px solid var(--text)" }}>
                <h2 className="pl-label">Valeur sélectionnée</h2>
                {!selectedSecurity ? (
                  <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                    Sélectionnez une valeur dans la liste.
                  </div>
                ) : (
                  <>
                    <div>
                      <div className="text-[18px] font-bold">{selectedSecurity.name}</div>
                      <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                        {selectedSecurity.symbol} · {selectedSecurity.sector}
                      </div>
                    </div>
                    <div style={{ background: "var(--panel-alt)", overflow: "hidden" }}>
                      <CandlestickChart
                        candles={priceItems}
                        loading={pricesLoading}
                        error={pricesError}
                        context={selectedPattern?.context ?? null}
                        indexOffset={indexOffset}
                        takeProfit={selectedDecision?.take_profit ?? null}
                        stopLoss={selectedDecision?.stop_loss ?? null}
                        width={320}
                        mono
                      />
                    </div>
                    <div className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-dim)" }}>
                      {selectedPattern ? (
                        <>
                          <span className="inline-block w-3.5" style={{ borderTop: "1.5px dashed var(--text)" }} />
                          Figure détectée par George : {selectedPattern.pattern_type}
                        </>
                      ) : (
                        "Aucune figure active détectée pour ce titre."
                      )}
                    </div>
                    <dl className="m-0 grid gap-x-3 gap-y-1 text-[11.5px]" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                      <dt style={{ color: "var(--text-dim)" }}>Pattern détecté</dt>
                      <dd className="m-0 text-right font-semibold">{selectedPattern?.pattern_type ?? "—"}</dd>
                      <dt style={{ color: "var(--text-dim)" }}>Confiance</dt>
                      <dd className="m-0 text-right font-semibold">
                        {selectedPattern ? `${Math.round(selectedPattern.confidence)}%` : "—"}
                      </dd>
                      <dt style={{ color: "var(--text-dim)" }}>Décision</dt>
                      <dd className="m-0 text-right">
                        {selectedDecision ? (
                          <span className={decisionTagClass(selectedDecision.decision_type)}>
                            {selectedDecision.decision_type}
                          </span>
                        ) : (
                          "—"
                        )}
                      </dd>
                    </dl>
                    {selectedDecision && (
                      <>
                        <div className="grid gap-2 text-center" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                          <div className="p-2" style={{ background: "var(--text)", color: "var(--bg)" }}>
                            <div className="pl-label">Take-profit</div>
                            <div className="text-[14px] font-bold mt-0.5">
                              {selectedDecision.take_profit != null ? `${selectedDecision.take_profit.toFixed(2)} €` : "—"}
                            </div>
                          </div>
                          <div className="p-2" style={{ border: "1px solid var(--text)" }}>
                            <div className="pl-label">Stop-loss</div>
                            <div className="text-[14px] font-bold mt-0.5">
                              {selectedDecision.stop_loss != null ? `${selectedDecision.stop_loss.toFixed(2)} €` : "—"}
                            </div>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            className="pl-btn pl-btn--solid"
                            style={{ flex: "1 1 140px", minHeight: 40 }}
                            onClick={() => setDockMsg(`Niveaux validés pour ${selectedSymbol}.`)}
                          >
                            Valider les niveaux
                          </button>
                          <button
                            className="pl-btn"
                            style={{ flex: "1 1 100px", minHeight: 40 }}
                            onClick={() => setDockMsg(`Ajustement des niveaux pour ${selectedSymbol} en cours de discussion.`)}
                          >
                            Ajuster
                          </button>
                        </div>
                      </>
                    )}
                  </>
                )}
              </section>

              {selectedSecurity && (
                <Panel title="Raisonnement / George">
                  <pre className="m-0 text-[11.5px] leading-relaxed whitespace-pre-wrap" style={{ fontFamily: "inherit" }}>
                    {reasoningLines.map((line, i) => `${String(31 + i).padStart(3, "0")}  ${line}`).join("\n")}
                  </pre>
                  <p className="m-0 text-[12px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                    {selectedDecision?.rationale ??
                      (selectedDecision
                        ? "Aucune note courte pour cette décision — demandez l'explication complète à George."
                        : "Aucune décision enregistrée pour ce titre — posez une question à George dans la barre en bas si vous voulez son avis.")}
                  </p>
                  {selectedDecision && (
                    <button
                      className="pl-btn self-start"
                      disabled={explainMutation.isPending}
                      onClick={() => {
                        const title = `George explique — ${selectedSymbol}`;
                        setPopup({ title, status: "loading", text: null });
                        explainMutation.mutate(
                          { decisionId: selectedDecision.id },
                          {
                            onSuccess: (data) => setPopup({ title, status: "done", text: data.explanation }),
                            onError: (err) => setPopup({ title, status: "error", text: err.message }),
                          }
                        );
                      }}
                    >
                      {explainMutation.isPending ? "George réfléchit…" : "Demander une analyse à George →"}
                    </button>
                  )}
                </Panel>
              )}
            </div>
          </div>

          {/* Grille de panneaux */}
          <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
            <Panel title="Journal / sous-agents">
              {agentEvents.length === 0 ? (
                <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucun événement — les sous-agents de veille alimentent ce journal.
                </div>
              ) : (
                <div className="grid text-[11.5px] leading-snug" style={{ gridTemplateColumns: "44px 108px minmax(0, 1fr)", gap: "3px 8px" }}>
                  {agentEvents.slice(0, 9).map((e) => (
                    <div key={e.id} className="contents">
                      <span style={{ color: "var(--text-dim)" }}>{time(e.created_at)}</span>
                      <span className="font-bold overflow-hidden text-ellipsis whitespace-nowrap">{e.agent_name}</span>
                      <span className="overflow-hidden text-ellipsis whitespace-nowrap" title={e.description}>
                        {e.description}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Watchlist / figures actives" label="Watchlist" className="pl-wide">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                  Univers suivi — CAC 40 &amp; CAC Mid 60
                </span>
                <div role="group" aria-label="Filtrer par décision" className="flex flex-wrap gap-1">
                  {FILTERS.map((f) => (
                    <button
                      key={f}
                      className="pl-btn"
                      style={{ minHeight: 30, padding: "0 10px", fontSize: 10.5 }}
                      aria-pressed={filter === f}
                      onClick={() => setFilter(f)}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
              {!securitiesError && !securitiesLoading && securities.length === 0 && (
                <EmptyState>
                  Aucun titre en base. Lancez <code>python -m ingestion.seed</code> puis <code>python -m ingestion.ohlcv</code>.
                </EmptyState>
              )}
              {!securitiesError && securities.length > 0 && (
                <div className="overflow-x-auto gd-scrollbar" style={{ maxHeight: 420 }}>
                  <table className="w-full border-collapse" style={{ minWidth: 620 }}>
                    <thead>
                      <tr>
                        {["Valeur", "Secteur", "Tendance", "Pattern", "Confiance", "Décision"].map((h) => (
                          <th
                            key={h}
                            scope="col"
                            className="pl-label text-left"
                            style={{
                              color: "var(--text-dim)",
                              padding: "4px 6px",
                              borderBottom: "1px solid var(--text)",
                              position: "sticky",
                              top: 0,
                              background: "var(--panel)",
                            }}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((security) => (
                        <WatchlistRow
                          key={security.symbol}
                          security={security}
                          decision={decisionsMap[security.symbol]}
                          selected={selectedSymbol === security.symbol}
                          onSelect={setSelected}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>

            <Panel title="George Index / paniers" label="Indices des paniers">
              {georgeBaskets.length === 0 ? (
                <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucun panier. Lancez <code>python -m ingestion.seed_demo</code>.
                </div>
              ) : (
                georgeBaskets.map((b) => <GeorgeIndexTile key={b.id} basketId={b.id} basketName={b.name} />)
              )}
              <div className="text-[10.5px]" style={{ color: "var(--text-dim)" }}>
                1 case = 2 points · rempli = score atteint
              </div>
            </Panel>

            {selectedSecurity && (
              <Panel title={`Fondamentaux / ${selectedSecurity.symbol}`} label="Fondamentaux">
                <dl className="m-0 grid gap-x-3 gap-y-1 text-[11.5px]" style={{ gridTemplateColumns: "minmax(0, 1fr) auto" }}>
                  {[
                    ["Secteur", selectedFundamentals?.sector ?? "—"],
                    ["Industrie", selectedFundamentals?.industry ?? "—"],
                    [
                      "Capitalisation",
                      selectedFundamentals?.market_cap != null
                        ? `${(selectedFundamentals.market_cap / 1e9).toFixed(2)} Md ${selectedFundamentals.currency ?? ""}`
                        : "—",
                    ],
                    ["PER (trailing)", selectedFundamentals?.trailing_pe != null ? selectedFundamentals.trailing_pe.toFixed(1) : "—"],
                    [
                      "Rendement dividende",
                      selectedFundamentals?.dividend_yield != null ? `${selectedFundamentals.dividend_yield.toFixed(2)}%` : "—",
                    ],
                  ].map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt style={{ color: "var(--text-dim)" }}>{k}</dt>
                      <dd className="m-0 text-right font-semibold">{v}</dd>
                    </div>
                  ))}
                </dl>
                {(selectedDividendsPage?.items?.length ?? 0) > 0 && (
                  <>
                    <div className="pl-label mt-1" style={{ color: "var(--text-dim)" }}>
                      Derniers dividendes
                    </div>
                    {selectedDividendsPage.items.map((d) => (
                      <div key={d.ex_date} className="flex justify-between text-[11.5px]">
                        <span style={{ color: "var(--text-dim)" }}>{d.ex_date}</span>
                        <span className="font-semibold">
                          {d.amount.toFixed(2)} {selectedFundamentals?.currency ?? ""}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </Panel>
            )}

            <Panel title={`${agentSummary.length} sous-agents / dispatch`} label="Sous-agents">
              {agentSummary.length === 0 ? (
                <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucun sous-agent actif récemment.
                </div>
              ) : (
                <div className="grid gap-x-3.5 gap-y-1.5" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                  {agentSummary.map((a) => (
                    <div key={a.name} className="flex flex-col gap-0.5 min-w-0">
                      <div className="flex justify-between gap-1.5 text-[11px]">
                        <span className="font-bold overflow-hidden text-ellipsis whitespace-nowrap">{a.name}</span>
                        <span style={{ color: "var(--text-dim)" }}>{AGENT_STATUS_LABEL[a.status] ?? a.status}</span>
                      </div>
                      <div style={{ height: 8, background: "var(--accent-dim)" }}>
                        <div
                          className={a.status === "validated" ? "" : "pl-hatch"}
                          style={{
                            height: 8,
                            width: `${Math.round((a.count / maxAgentCount) * 100)}%`,
                            background: a.status === "validated" ? "var(--text)" : undefined,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <div className="text-[10.5px]" style={{ color: "var(--text-dim)" }}>
                barre = événements récents · plein = validé, hachures = en attente ou quarantaine
              </div>
            </Panel>

            <Panel title="Marché d'énergie" label="Marché d'énergie">
              {sortedEnergyPrices.length === 0 ? (
                <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                  Aucune donnée pour l'instant (import quotidien pas encore passé).
                </div>
              ) : (
                <div className="grid gap-x-3 gap-y-0.5 text-[11.5px]" style={{ gridTemplateColumns: "minmax(0, 1fr) auto auto" }}>
                  {sortedEnergyPrices.map((e) => {
                    const up = (e.change_24h_pct ?? 0) >= 0;
                    return (
                      <div key={e.commodity_code} className="contents">
                        <span style={{ color: "var(--text-dim)" }}>{ENERGY_LABELS[e.commodity_code] ?? e.commodity_code}</span>
                        <span className="text-right">
                          {e.price.toFixed(2)} {e.currency}
                        </span>
                        <span className="text-right font-bold">
                          <span aria-hidden="true">{up ? "▲" : "▼"}</span>
                          <span className="sr-only">{up ? "en hausse" : "en baisse"}</span>
                          {e.change_24h_pct != null ? ` ${Math.abs(e.change_24h_pct).toFixed(2)} %` : ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </Panel>
          </div>

          {/* Dock */}
          <section
            aria-label="Poser une question à George"
            className="sticky bottom-0 flex flex-col gap-2 px-3 py-2.5 mb-4"
            style={{ border: "1px solid var(--text)", background: "var(--bg)" }}
          >
            <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
              {dockMsg ?? "Sélectionnez une valeur pour voir le raisonnement complet, ou posez une question."}
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              <label htmlFor="ask-george" className="pl-label whitespace-nowrap">
                George explique ›
              </label>
              <input
                id="ask-george"
                className="text-[12px] px-2.5"
                style={{
                  flex: "999 1 320px",
                  minWidth: 0,
                  minHeight: 40,
                  fontFamily: "inherit",
                  border: "1px solid var(--text)",
                  background: "var(--bg)",
                  color: "var(--text)",
                }}
                placeholder="Poser une question à George…"
                disabled={chatMutation.isPending}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.currentTarget.value.trim()) {
                    const question = e.currentTarget.value.trim();
                    e.currentTarget.value = "";
                    askGeorge(question);
                  }
                }}
              />
              <button className="pl-btn pl-btn--solid inline-flex items-center gap-2" style={{ minHeight: 40 }} onClick={voice.start}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <rect x="9" y="3" width="6" height="11" rx="3" />
                  <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
                </svg>
                Commande vocale
              </button>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
