import { useMemo, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import GeorgeIndexTile from "../components/GeorgeIndexTile";
import ResponsePopup from "../components/ResponsePopup";
import WatchlistRow from "../components/WatchlistRow";
import { decisionColor, macro } from "../data";
import { useVoiceCapture } from "../hooks/useVoiceCapture";
import {
  useAgentActivity,
  useBaskets,
  useChat,
  useDecisions,
  useExplainDecision,
  useRefreshPrices,
  useSecurities,
  useSecurityDividends,
  useSecurityFundamentals,
  useSecurityPatterns,
  useSecurityPrices,
  useTriggerCollection,
} from "../api/queries";

const FILTERS = ["Tous", "Achat", "Surveiller", "Alléger"];

const SIDEBAR_NAV = [{ icon: "◆", label: "Univers", active: true }];

function EmptyState({ children }) {
  return (
    <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
      {children}
    </div>
  );
}

export default function Univers() {
  const [filter, setFilter] = useState("Tous");
  const [selected, setSelected] = useState(null);
  const [dockMsg, setDockMsg] = useState(null);
  const [popup, setPopup] = useState(null); // { title, status: "listening"|"loading"|"done"|"error", text }
  const chatMutation = useChat();
  const explainMutation = useExplainDecision();
  const refreshPricesMutation = useRefreshPrices();

  function refreshPrices() {
    setPopup({
      title: "Mise à jour des prix",
      status: "loading",
      text: null,
      loadingText: "Téléchargement des prix en cours (jusqu'à une minute pour tout l'univers)…",
    });
    refreshPricesMutation.mutate(undefined, {
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
      onError: (err) => setPopup({ title: "Mise à jour des prix", status: "error", text: err.message }),
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

  const { data: securitiesPage, isLoading: securitiesLoading, isError: securitiesError } = useSecurities({ limit: 200 });
  const { data: decisionsPage } = useDecisions({ limit: 200 });
  const { data: basketsPage } = useBaskets();
  const { data: agentPage } = useAgentActivity({ limit: 6 });

  const securities = securitiesPage?.items ?? [];

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
  const { data: selectedPricesPage } = useSecurityPrices(selectedSymbol, { limit: 250 });
  const { data: selectedFundamentals } = useSecurityFundamentals(selectedSymbol);
  const { data: selectedDividendsPage } = useSecurityDividends(selectedSymbol, { limit: 5 });

  const selectedPattern = selectedPatternsPage?.items?.[0] ?? null;
  const priceItems = selectedPricesPage?.items ?? [];
  // `items` ne contient que les `limit` séances les plus récentes : l'écart
  // entre `total` et leur nombre est le décalage à soustraire aux indices
  // absolus du `context` d'un pattern pour les replacer dans ce sous-ensemble.
  const indexOffset = selectedPricesPage ? selectedPricesPage.total - priceItems.length : 0;

  const georgeBaskets = (basketsPage ?? []).slice(0, 2);
  // Toujours exactement 2 emplacements (tuile ou vide) : la grille a des
  // colonnes fixes (150px/150px/1fr) et un nombre variable d'éléments
  // décalerait la tuile macro dans la mauvaise colonne.
  const georgeSlots = Array.from({ length: 2 }, (_, i) => georgeBaskets[i] ?? null);
  const agentEvents = agentPage?.items ?? [];

  return (
    <>
    <ResponsePopup popup={popup} onClose={closePopup} onStopListening={voice.stop} />
    <div className="grid h-full" style={{ gridTemplateRows: "1fr 84px" }}>
      <div className="grid h-full overflow-hidden" style={{ gridTemplateColumns: "190px 1fr 340px" }}>
        {/* Sidebar */}
        <div
          className="border-r px-2.5 py-4.5 flex flex-col gap-0.5"
          style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}
        >
          <div className="text-[10.5px] uppercase tracking-widest px-2.5 pt-2.5 pb-1.5" style={{ color: "var(--text-dim)" }}>
            Navigation
          </div>
          {SIDEBAR_NAV.map((item) => (
            <div
              key={item.label}
              className="flex items-center gap-2.5 text-[13px] font-medium px-2.5 py-2 rounded-lg"
              style={{
                color: item.active ? "var(--text)" : "var(--text-dim)",
                background: item.active ? "var(--accent-dim)" : "transparent",
              }}
            >
              <span className="w-4 text-center opacity-85">{item.icon}</span>
              {item.label}
            </div>
          ))}
          <button
            onClick={refreshPrices}
            disabled={refreshPricesMutation.isPending}
            className="flex items-center gap-2.5 text-[13px] font-medium px-2.5 py-2 rounded-lg text-left w-full border-0 bg-transparent"
            style={{ color: "var(--text-dim)" }}
          >
            <span className="w-4 text-center opacity-85">🔄</span>
            {refreshPricesMutation.isPending ? "Mise à jour…" : "Mise à jour des prix"}
          </button>
          <button
            onClick={triggerMacroCollection}
            disabled={triggerCollectionMutation.isPending}
            className="flex items-center gap-2.5 text-[13px] font-medium px-2.5 py-2 rounded-lg text-left w-full border-0 bg-transparent"
            style={{ color: "var(--text-dim)" }}
          >
            <span className="w-4 text-center opacity-85">🌍</span>
            {triggerCollectionMutation.isPending ? "Collecte…" : "Collecte macro"}
          </button>
        </div>

        {/* Watchlist + tiles */}
        <div className="overflow-y-auto px-4.5 py-4 gd-scrollbar">
          <div className="flex items-center justify-between mb-3.5">
            <div>
              <div className="display text-[16px] font-semibold">Univers suivi — CAC 40 &amp; CAC Mid 60</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                {securitiesLoading ? "Chargement…" : `${securities.length} valeurs`}
              </div>
            </div>
            <div className="flex gap-1.5">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className="text-[11.5px] px-3 py-1.5 rounded-full border"
                  style={{
                    background: filter === f ? "var(--accent)" : "transparent",
                    borderColor: filter === f ? "var(--accent)" : "var(--hairline)",
                    color: filter === f ? "#fff" : "var(--text-dim)",
                  }}
                >
                  {f}
                </button>
              ))}
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
          {!securitiesError && securities.length > 0 && (
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  {["Valeur", "Secteur", "Tendance", "Pattern", "Confiance", "Décision"].map((h) => (
                    <th
                      key={h}
                      className="text-left text-[10.5px] uppercase tracking-wider font-medium px-2.5 py-2 border-b"
                      style={{ color: "var(--text-dim)", borderColor: "var(--hairline)" }}
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
          )}

          <div className="grid gap-3 mt-4" style={{ gridTemplateColumns: "150px 150px 1fr" }}>
            {georgeBaskets.length === 0 ? (
              // col-span-2 : sans ça, la grille à colonnes fixes (150px/150px/1fr)
              // décale la tuile macro dans la 2e colonne (150px) au lieu de la 3e (1fr).
              <div
                className="col-span-2 border rounded-[10px] p-3 flex items-center text-[11px]"
                style={{ borderColor: "var(--hairline)", background: "var(--panel)", color: "var(--text-dim)" }}
              >
                Aucun panier. Lancez <code>python -m ingestion.seed_demo</code>.
              </div>
            ) : (
              georgeSlots.map((b, i) =>
                b ? (
                  <GeorgeIndexTile key={b.id} basketId={b.id} basketName={b.name} />
                ) : (
                  <div key={`empty-slot-${i}`} className="border rounded-[10px]" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }} />
                )
              )
            )}
            <div className="border rounded-[10px] p-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
                Repères macro
              </div>
              {macro.map((m) => (
                <div key={m.name} className="flex justify-between items-center text-xs py-0.5">
                  <span style={{ color: "var(--text-dim)" }}>{m.name}</span>
                  <span className="mono" style={{ color: m.dir === "up" ? "var(--positive)" : "var(--negative)" }}>
                    {m.dir === "up" ? "▲" : "▼"} {m.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Detail panel */}
        <div className="border-l overflow-y-auto flex flex-col" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
          {!selectedSecurity ? (
            <div className="p-5 text-[13px]" style={{ color: "var(--text-dim)" }}>
              Sélectionnez une valeur dans la liste.
            </div>
          ) : (
            <>
              <div className="px-5 pt-5">
                <h2 className="display text-[19px] font-semibold mb-0.5">{selectedSecurity.name}</h2>
                <div className="text-[12.5px] mb-4" style={{ color: "var(--text-dim)" }}>
                  {selectedSecurity.symbol} · {selectedSecurity.sector}
                </div>
                <div className="border rounded-[10px] mb-4 overflow-hidden" style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)" }}>
                  <CandlestickChart
                    candles={priceItems}
                    context={selectedPattern?.context ?? null}
                    indexOffset={indexOffset}
                    takeProfit={selectedDecision?.take_profit ?? null}
                    stopLoss={selectedDecision?.stop_loss ?? null}
                  />
                </div>
                <div className="flex items-center gap-1.5 -mt-2.5 mb-3 text-[11px]" style={{ color: "var(--text-dim)" }}>
                  {selectedPattern ? (
                    <>
                      <span className="inline-block w-3.5" style={{ borderTop: "1.5px dashed var(--accent)" }} />
                      Figure détectée par George : {selectedPattern.pattern_type}
                    </>
                  ) : (
                    "Aucune figure active détectée pour ce titre."
                  )}
                </div>

                <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                  Raisonnement de George
                </div>
                <div className="text-[13px] leading-relaxed" style={{ color: "var(--text-dim)" }}>
                  {selectedDecision?.rationale ??
                    (selectedDecision
                      ? "Aucune note courte pour cette décision — demandez l'explication complète à George."
                      : "Aucune décision enregistrée pour ce titre — posez une question à George dans la barre en bas si vous voulez son avis.")}
                </div>
                {selectedDecision && (
                  <button
                    className="mt-2 text-[11.5px] px-3 py-1.5 rounded-full border"
                    style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
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
                    {explainMutation.isPending ? "George réfléchit…" : "Demander une analyse à George"}
                  </button>
                )}

                <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                  Paramètres
                </div>
                {[
                  ["Pattern détecté", selectedPattern?.pattern_type ?? "—"],
                  ["Confiance", selectedPattern ? `${Math.round(selectedPattern.confidence)}%` : "—"],
                  ["Décision", selectedDecision?.decision_type ?? "—"],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between text-[13px] py-1.5 border-b" style={{ borderColor: "var(--hairline)" }}>
                    <span style={{ color: "var(--text-dim)" }}>{k}</span>
                    <span className="mono" style={{ color: k === "Décision" && selectedDecision ? decisionColor(selectedDecision.decision_type) : "var(--text)" }}>
                      {v}
                    </span>
                  </div>
                ))}

                <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                  Fondamentaux
                </div>
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
                  <div key={k} className="flex justify-between text-[13px] py-1.5 border-b" style={{ borderColor: "var(--hairline)" }}>
                    <span style={{ color: "var(--text-dim)" }}>{k}</span>
                    <span className="mono" style={{ color: "var(--text)" }}>{v}</span>
                  </div>
                ))}
                {(selectedDividendsPage?.items?.length ?? 0) > 0 && (
                  <>
                    <div className="text-[11px] mt-3 mb-1" style={{ color: "var(--text-dim)" }}>
                      Derniers dividendes
                    </div>
                    {selectedDividendsPage.items.map((d) => (
                      <div key={d.ex_date} className="flex justify-between text-[12px] py-1" style={{ color: "var(--text-dim)" }}>
                        <span>{d.ex_date}</span>
                        <span className="mono">
                          {d.amount.toFixed(2)} {selectedFundamentals?.currency ?? ""}
                        </span>
                      </div>
                    ))}
                  </>
                )}

                {selectedDecision && (
                  <>
                    <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                      Niveaux proposés
                    </div>
                    <div className="flex gap-2.5 mt-2.5">
                      <div className="flex-1 border rounded-lg p-2.5 text-center" style={{ borderColor: "var(--hairline)" }}>
                        <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                          Take-profit
                        </div>
                        <div className="mono font-semibold text-[15px] mt-1" style={{ color: "var(--positive)" }}>
                          {selectedDecision.take_profit != null ? `${selectedDecision.take_profit.toFixed(2)} €` : "—"}
                        </div>
                      </div>
                      <div className="flex-1 border rounded-lg p-2.5 text-center" style={{ borderColor: "var(--hairline)" }}>
                        <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                          Stop-loss
                        </div>
                        <div className="mono font-semibold text-[15px] mt-1" style={{ color: "var(--negative)" }}>
                          {selectedDecision.stop_loss != null ? `${selectedDecision.stop_loss.toFixed(2)} €` : "—"}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-3.5">
                      <button
                        className="flex-1 py-2.5 rounded-lg font-semibold text-[13px]"
                        style={{ background: "var(--accent)", color: "#fff" }}
                        onClick={() => setDockMsg(`Niveaux validés pour ${selectedSymbol}.`)}
                      >
                        Valider les niveaux
                      </button>
                      <button
                        className="flex-1 py-2.5 rounded-lg font-semibold text-[13px] border"
                        style={{ borderColor: "var(--hairline)" }}
                        onClick={() => setDockMsg(`Ajustement des niveaux pour ${selectedSymbol} en cours de discussion.`)}
                      >
                        Ajuster
                      </button>
                    </div>
                  </>
                )}
              </div>

              <div className="px-5 pb-5 mt-1.5">
                <div className="text-[11px] uppercase tracking-wider mb-2">Sous-agents — activité récente</div>
                {agentEvents.length === 0 && (
                  <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                    Aucun événement — les sous-agents de veille arrivent en Phase 7.
                  </div>
                )}
                {agentEvents.map((e) => (
                  <div
                    key={e.id}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-md mb-1.5 text-[11.5px]"
                    style={{
                      background: "var(--panel-alt)",
                      borderLeft: `3px solid ${
                        e.status === "validated" ? "var(--positive)" : e.status === "pending" ? "var(--warning)" : "var(--negative)"
                      }`,
                    }}
                  >
                    <span className="mono font-semibold w-[92px] flex-shrink-0">{e.agent_name}</span>
                    <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--text-dim)" }}>
                      {e.description}
                    </span>
                    <span className="mono text-[10.5px] flex-shrink-0" style={{ color: "var(--text-dim)" }}>
                      {new Date(e.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Dock */}
      <div className="border-t px-5 py-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
        <div className="flex items-center gap-2.5">
          <div className="display font-semibold text-[13px] whitespace-nowrap" style={{ color: "var(--accent)" }}>
            George explique ›
          </div>
          <div className="text-[13px] flex-1" style={{ color: "var(--text-dim)" }}>
            {dockMsg ?? "Sélectionnez une valeur pour voir le raisonnement complet, ou posez une question."}
          </div>
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg px-3 py-2.5 text-[13px] border"
            style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text)" }}
            placeholder="Poser une question à George…"
            disabled={chatMutation.isPending}
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.currentTarget.value.trim()) {
                const question = e.currentTarget.value.trim();
                e.currentTarget.value = "";
                setPopup({ title: "George répond", status: "loading", text: null });
                chatMutation.mutate(question, {
                  onSuccess: (data) => setPopup({ title: "George répond", status: "done", text: data.answer }),
                  onError: (err) => setPopup({ title: "George répond", status: "error", text: err.message }),
                });
              }
            }}
          />
          <button
            className="text-xs px-3 py-1.5 rounded-full border whitespace-nowrap"
            style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text-dim)" }}
            onClick={voice.start}
          >
            🎙 Commande vocale
          </button>
        </div>
      </div>
    </div>
    </>
  );
}
