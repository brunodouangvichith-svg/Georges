import { useEffect, useMemo, useRef, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import ResponsePopup from "../components/ResponsePopup";
import RiskMetrics from "../components/RiskMetrics";
import UniversTorus from "../components/UniversTorus";
import { decisionTagClass } from "../data";
import { useElementWidth } from "../hooks/useElementWidth";
import {
  useDecisions,
  useLatestPatterns,
  useRefreshPrices,
  useRiskMetrics,
  useSecurities,
  useSecurityDividends,
  useSecurityFundamentals,
  useSecurityPatterns,
  useSecurityPrices,
  useTriggerCollection,
} from "../api/queries";

// Écran Univers — tore 3D, puis côte à côte la fiche de la valeur sélectionnée
// et ses fondamentaux, dans le thème George d'origine (bleu nuit, blanc, accent
// bleu ; vert/orange/rouge pour les décisions). Toutes les données affichées
// viennent de l'API : aucun chiffre de démonstration ici.

function EmptyState({ children }) {
  return (
    <div className="text-[12px] p-3 border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
      {children}
    </div>
  );
}

function Panel({ title, children, className = "", style, label }) {
  return (
    <section aria-label={label ?? title} className={`gd-panel ${className}`} style={style}>
      <h2 className="gd-label">{title}</h2>
      {children}
    </section>
  );
}


export default function Univers() {
  const [selected, setSelected] = useState(null);
  const [popup, setPopup] = useState(null); // { title, status: "listening"|"loading"|"done"|"error", text }
  // Le graphique en chandeliers prend la largeur de son cadre.
  const [chartRef, chartWidth] = useElementWidth();
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

  function closePopup() {
    setPopup(null);
  }

  const { data: securitiesPage, isLoading: securitiesLoading, isError: securitiesError } = useSecurities({ limit: 200 });
  const { data: decisionsPage } = useDecisions({ limit: 200 });
  const { data: riskData, isLoading: riskLoading, isError: riskError } = useRiskMetrics();

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

  const sortedSecurities = useMemo(
    () => [...securities].sort((a, b) => a.name.localeCompare(b.name, "fr")),
    [securities],
  );

  const selectedSymbol = selected ??securities[0]?.symbol ?? null;
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
  // `items` ne contient que les `limit` séances les plus récentes : l'écart
  // entre `total` et leur nombre est le décalage à soustraire aux indices
  // absolus du `context` d'un pattern pour les replacer dans ce sous-ensemble.
  const indexOffset = selectedPricesPage ? selectedPricesPage.total - priceItems.length : 0;

  return (
    <>
      <ResponsePopup popup={popup} onClose={closePopup} />
      <div className="h-full overflow-y-auto gd-scrollbar">
        <div className="mx-auto flex flex-col gap-3.5 px-5 pt-4" style={{ maxWidth: 1440 }}>
          {/* En-tête */}
          <header className="flex flex-wrap items-start justify-between" style={{ gap: "16px 40px" }}>
            <div className="flex flex-col gap-1" style={{ minWidth: 260 }}>
              <h1 className="display m-0 text-[20px] font-semibold">
                George / <span>Univers</span>
              </h1>
              <div className="gd-label" style={{ color: "var(--text-dim)" }}>
                CAC 40 &amp; CAC Mid 60 → décisions expliquées
              </div>
            </div>
          </header>

          {/* Barre d'actions */}
          <div
            className="flex flex-wrap items-center gap-2.5 pt-2 text-[11px]"
            style={{ borderTop: "1px solid var(--hairline)", color: "var(--text-dim)" }}
          >
            <span>{securitiesLoading ? "Chargement…" : `${securities.length} valeurs suivies`}</span>
            <div className="ml-auto flex flex-wrap gap-1.5">
              <button className="gd-btn" onClick={refreshPrices} disabled={refreshPricesMutation.isPending}>
                {refreshPricesMutation.isPending ? "Mise à jour…" : "Mise à jour des prix"}
              </button>
              <button className="gd-btn" onClick={triggerMacroCollection} disabled={triggerCollectionMutation.isPending}>
                {triggerCollectionMutation.isPending ? "Collecte…" : "Collecte macro"}
              </button>
            </div>
          </div>

          {securitiesError && (
            <EmptyState>
              Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
            </EmptyState>
          )}

          {!securitiesError && !securitiesLoading && securities.length === 0 && (
            <EmptyState>
              Aucun titre en base. Lancez <code>python -m ingestion.seed</code> puis <code>python -m ingestion.ohlcv</code>.
            </EmptyState>
          )}

          {/* Tore 3D */}
          <section aria-label="Tore 3D de l'univers">
            {securities.length > 0 ? (
              <UniversTorus
                securities={securities}
                patternsBySymbol={patternsBySymbol}
                decisionsMap={decisionsMap}
                selectedSymbol={selectedSymbol}
                onSelect={setSelected}
              />
            ) : (
              <div className="flex items-center justify-center text-[12px]" style={{ minHeight: 320, color: "var(--text-dim)" }}>
                {securitiesLoading ? "Chargement de l'univers…" : "Le tore s'affichera dès que des titres seront en base."}
              </div>
            )}
          </section>

          {/* Sous le tore : valeur sélectionnée et fondamentaux côte à côte
              (l'un sous l'autre quand la place manque) */}
          <div className="flex flex-wrap items-start gap-3 pb-3.5">
            <section aria-label="Valeur sélectionnée" className="gd-panel" style={{ flex: "999 1 520px", minWidth: 0 }}>
              <h2 className="gd-label">Valeur sélectionnée</h2>
              {securities.length > 0 && (
                <select
                  aria-label="Choisir une valeur"
                  className="w-full rounded-lg border px-2 text-[12.5px]"
                  style={{ minHeight: 36, background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text)" }}
                  value={selectedSymbol ?? ""}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {sortedSecurities.map((s) => (
                    <option key={s.symbol} value={s.symbol}>
                      {s.name} ({s.symbol})
                    </option>
                  ))}
                </select>
              )}
              {!selectedSecurity ? (
                <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                  Aucune valeur à afficher.
                </div>
              ) : (
                <>
                  <div>
                    <div className="text-[18px] font-bold">{selectedSecurity.name}</div>
                    <div className="text-[11.5px]" style={{ color: "var(--text-dim)" }}>
                      {selectedSecurity.symbol} · {selectedSecurity.sector}
                    </div>
                  </div>
                  <div ref={chartRef} style={{ background: "var(--panel-alt)", overflow: "hidden" }}>
                    <CandlestickChart
                      candles={priceItems}
                      loading={pricesLoading}
                      error={pricesError}
                      context={selectedPattern?.context ?? null}
                      indexOffset={indexOffset}
                      takeProfit={selectedDecision?.take_profit ?? null}
                      stopLoss={selectedDecision?.stop_loss ?? null}
                      width={chartWidth ?? 320}
                    />
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px]" style={{ color: "var(--text-dim)" }}>
                    {selectedPattern ? (
                      <>
                        <span className="inline-block w-3.5" style={{ borderTop: "1.5px dashed var(--accent)" }} />
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
                  <RiskMetrics
                    metrics={riskData?.items?.find((m) => m.symbol === selectedSymbol)}
                    index={riskData?.index}
                    loading={riskLoading}
                    error={riskError && !riskData}
                  />
                  {selectedDecision && (
                    <>
                      <div className="grid gap-2 text-center" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                        <div className="p-2 rounded-lg border" style={{ borderColor: "var(--hairline)" }}>
                          <div className="gd-label">Take-profit</div>
                          <div className="mono text-[15px] font-semibold mt-0.5" style={{ color: "var(--positive)" }}>
                            {selectedDecision.take_profit != null ? `${selectedDecision.take_profit.toFixed(2)} €` : "—"}
                          </div>
                        </div>
                        <div className="p-2 rounded-lg border" style={{ borderColor: "var(--hairline)" }}>
                          <div className="gd-label">Stop-loss</div>
                          <div className="mono text-[15px] font-semibold mt-0.5" style={{ color: "var(--negative)" }}>
                            {selectedDecision.stop_loss != null ? `${selectedDecision.stop_loss.toFixed(2)} €` : "—"}
                          </div>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="gd-btn gd-btn--solid"
                          style={{ flex: "1 1 140px", minHeight: 40 }}
                          onClick={() =>
                            setPopup({ title: "Niveaux", status: "done", text: `Niveaux validés pour ${selectedSymbol}.` })
                          }
                        >
                          Valider les niveaux
                        </button>
                        <button
                          className="gd-btn"
                          style={{ flex: "1 1 100px", minHeight: 40 }}
                          onClick={() =>
                            setPopup({
                              title: "Niveaux",
                              status: "done",
                              text: `Ajustement des niveaux pour ${selectedSymbol} en cours de discussion.`,
                            })
                          }
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
              <Panel
                title={`Fondamentaux / ${selectedSecurity.symbol}`}
                label="Fondamentaux"
                style={{ flex: "1 1 300px", minWidth: 0 }}
              >
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
                    <div className="gd-label mt-1" style={{ color: "var(--text-dim)" }}>
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
          </div>
        </div>
      </div>
    </>
  );
}
