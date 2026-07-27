import { useMemo, useRef, useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import GeorgeIndexTile from "../components/GeorgeIndexTile";
import WatchlistRow from "../components/WatchlistRow";
import { decisionColor, macro } from "../data";
import {
  useAgentActivity,
  useBaskets,
  useChat,
  useDecisions,
  useExplainDecision,
  useSecurities,
  useSecurityPatterns,
  useSecurityPrices,
} from "../api/queries";

const FILTERS = ["Tous", "Achat", "Surveiller", "Alléger"];

// La reconnaissance vocale de Chrome/Edge n'est pas locale : l'audio est
// envoyé aux serveurs de Google pour être transcrit, d'où un code "network"
// (pas un vrai problème de connexion Internet en général) si un bloqueur de
// pub/VPN/pare-feu d'entreprise empêche cette requête sortante.
const VOICE_ERROR_MESSAGES = {
  network: "Le micro n'a pas pu joindre le service de reconnaissance vocale de Google (utilisé par Chrome/Edge). Vérifiez un éventuel bloqueur de pub/extension de confidentialité, VPN, ou pare-feu d'entreprise qui bloquerait ce trafic sortant, puis réessayez.",
  "not-allowed": "Accès au micro refusé — autorisez-le dans les paramètres du navigateur pour ce site puis réessayez.",
  "no-speech": "Aucune parole détectée avant la fin de l'écoute — réessayez en parlant un peu plus fort ou plus vite après avoir cliqué.",
  "audio-capture": "Aucun micro détecté sur cet appareil.",
};

const SIDEBAR_NAV = [
  { icon: "◆", label: "Univers", active: true },
  { icon: "▤", label: "Paniers" },
  { icon: "✓", label: "Décisions" },
  { icon: "◔", label: "George Index" },
  { icon: "⏱", label: "Historique" },
];

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
  const recognitionRef = useRef(null);

  function closePopup() {
    // Coupe le micro si une écoute est en cours — sinon le navigateur
    // continue d'enregistrer alors que le popup est fermé.
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    setPopup(null);
  }

  function startVoiceCapture() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setPopup({
        title: "Commande vocale",
        status: "error",
        text: "La reconnaissance vocale n'est pas prise en charge par ce navigateur — essayez Chrome ou Edge.",
      });
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "fr-FR";
    recognition.continuous = false; // s'arrête d'elle-même dès qu'un silence est détecté
    recognition.interimResults = true;
    recognitionRef.current = recognition;

    setPopup({ title: "Commande vocale", status: "listening", text: "" });

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      setPopup((prev) => (prev?.status === "listening" ? { ...prev, text: transcript } : prev));
    };

    recognition.onerror = (event) => {
      recognitionRef.current = null;
      setPopup({ title: "Commande vocale", status: "error", text: VOICE_ERROR_MESSAGES[event.error] ?? `Erreur micro : ${event.error}` });
    };

    // Se déclenche automatiquement dès que la reconnaissance détecte un
    // silence (recognition.continuous = false) — pas besoin de minuterie
    // manuelle pour "terminer sur silence".
    recognition.onend = () => {
      recognitionRef.current = null;
      setPopup((prev) => {
        if (prev?.status !== "listening") return prev;
        const question = prev.text?.trim();
        if (!question) {
          return { title: "Commande vocale", status: "error", text: "Aucune parole détectée — réessayez." };
        }
        const title = `Commande vocale — « ${question} »`;
        chatMutation.mutate(question, {
          onSuccess: (data) => setPopup({ title, status: "done", text: data.answer }),
          onError: (err) => setPopup({ title, status: "error", text: err.message }),
        });
        return { title, status: "loading", text: null };
      });
    };

    recognition.start();
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
    {popup && (
      <div
        className="fixed inset-0 flex items-center justify-center z-50 px-6"
        style={{ background: "rgba(0,0,0,0.55)" }}
        onClick={closePopup}
      >
        <div
          className="max-w-lg w-full rounded-xl p-5 border"
          style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="display font-semibold text-[14px]" style={{ color: "var(--accent)" }}>
              {popup.title}
            </div>
            <button onClick={closePopup} style={{ color: "var(--text-dim)" }}>
              ✕
            </button>
          </div>
          {popup.status === "listening" ? (
            <div className="flex flex-col items-center gap-4 py-4">
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center text-[26px] gd-mic-pulse"
                style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
              >
                🎙
              </div>
              <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
                Je vous écoute… (s'arrête seul au silence)
              </div>
              <div className="text-[14px] text-center min-h-[20px]">{popup.text}</div>
              <button
                className="text-[11.5px] px-3 py-1.5 rounded-full border"
                style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
                onClick={() => recognitionRef.current?.stop()}
              >
                Arrêter l'écoute
              </button>
            </div>
          ) : (
            <div
              className="text-[13px] leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto"
              style={{ color: popup.status === "error" ? "var(--negative)" : "var(--text)" }}
            >
              {popup.status === "loading" ? "George réfléchit…" : popup.text}
            </div>
          )}
        </div>
      </div>
    )}
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
                    {explainMutation.isPending ? "George réfléchit…" : "Demander l'explication complète à George"}
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
            onClick={startVoiceCapture}
          >
            🎙 Commande vocale
          </button>
        </div>
      </div>
    </div>
    </>
  );
}
