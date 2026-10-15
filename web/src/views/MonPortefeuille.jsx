import { useRef, useState } from "react";
import Counter from "../components/Counter";
import ResponsePopup from "../components/ResponsePopup";
import { useVoiceCapture } from "../hooks/useVoiceCapture";
import {
  useAllocateBudget,
  useDeletePortfolio,
  usePortfolios,
  useRemoveDecisionFromPortfolio,
} from "../api/queries";
import { decisionColor } from "../data";

function pnlColor(value) {
  return value == null ? "var(--text-dim)" : value >= 0 ? "var(--positive)" : "var(--negative)";
}

function formatPnlPct(value) {
  return value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function formatAmount(value) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} €`;
}

// Extrait un montant en euros d'une phrase transcrite ("répartis un budget
// de 100 000 euros entre ces actions" -> 100000) — la reconnaissance vocale
// transcrit déjà les nombres en chiffres, donc une expression régulière
// suffit ici : pas besoin d'un appel LLM pour cette extraction.
function parseBudgetFromText(text) {
  const match = text.match(/(\d[\d\s.,]*)\s*(?:€|euros?)/i);
  if (!match) return null;
  const normalized = match[1].replace(/[\s.]/g, "").replace(",", ".");
  const value = parseFloat(normalized);
  return Number.isFinite(value) && value > 0 ? value : null;
}

export default function MonPortefeuille() {
  const { data: portfolios, isError } = usePortfolios();
  const deletePortfolioMutation = useDeletePortfolio();
  const removeDecisionMutation = useRemoveDecisionFromPortfolio();
  const allocateBudgetMutation = useAllocateBudget();

  const [popup, setPopup] = useState(null);
  // Quel portefeuille a déclenché l'écoute — une ref, pas un state : lue de
  // façon synchrone au clic (avant le rendu suivant), contrairement à un
  // state dont la mise à jour n'est pas encore visible dans le même geste.
  const activePortfolioIdRef = useRef(null);

  const voice = useVoiceCapture({
    onListening: () => setPopup({ title: "Demander à George", status: "listening", text: "" }),
    onInterim: (text) => setPopup((prev) => (prev?.status === "listening" ? { ...prev, text } : prev)),
    onError: (message) => setPopup({ title: "Demander à George", status: "error", text: message }),
    onFinal: (question) => {
      if (!question) {
        setPopup({ title: "Demander à George", status: "error", text: "Aucune parole détectée — réessayez." });
        return;
      }
      const budget = parseBudgetFromText(question);
      if (budget == null) {
        setPopup({
          title: "Demander à George",
          status: "error",
          text: `Je n'ai pas compris de montant en euros dans « ${question} ». Précisez par exemple « répartis un budget de 50 000 euros ».`,
        });
        return;
      }
      const title = `Demander à George — « ${question} »`;
      setPopup({ title, status: "loading", text: null });
      allocateBudgetMutation.mutate(
        { portfolioId: activePortfolioIdRef.current, budget },
        {
          onSuccess: (data) => setPopup({ title, status: "done", text: data.summary }),
          onError: (err) => setPopup({ title, status: "error", text: err.message }),
        }
      );
    },
  });

  function askGeorge(portfolioId) {
    activePortfolioIdRef.current = portfolioId;
    voice.start();
  }

  function closePopup() {
    voice.abort();
    setPopup(null);
  }

  const list = portfolios ?? [];
  const positions = list.reduce((n, p) => n + p.decisions.length, 0);
  const invested = list.reduce((sum, p) => sum + (p.total_invested ?? 0), 0);
  const pnlKnown = list.filter((p) => p.total_pnl_amount != null);
  const pnlTotal = pnlKnown.reduce((sum, p) => sum + p.total_pnl_amount, 0);
  const allPnlPcts = list.flatMap((p) => p.decisions.map((d) => d.pnl_pct)).filter((v) => v != null);
  const winners = allPnlPcts.filter((v) => v > 0).length;
  const losers = allPnlPcts.filter((v) => v < 0).length;

  return (
    <div className="h-full overflow-y-auto gd-scrollbar">
      <ResponsePopup popup={popup} onClose={closePopup} onStopListening={voice.stop} />
      <div className="mx-auto flex flex-col gap-3.5 px-5 pt-4 pb-6" style={{ maxWidth: 1440 }}>
        {/* En-tête + compteurs (même disposition qu'Univers) */}
        <header className="flex flex-wrap items-start justify-between" style={{ gap: "16px 40px" }}>
          <div className="flex flex-col gap-1" style={{ minWidth: 260 }}>
            <h1 className="display m-0 text-[20px] font-semibold">
              George / <span>Mon portefeuille</span>
            </h1>
            <div className="gd-label">Portefeuilles créés depuis Paniers → PnL en temps réel</div>
          </div>
          <div className="flex flex-wrap justify-end" style={{ gap: "14px 28px", flex: "1 1 600px" }}>
            <Counter label="Portefeuilles" value={list.length} ratio={1} />
            <Counter label="Positions" value={positions} ratio={1} />
            <Counter
              label="En gain"
              value={winners}
              ratio={allPnlPcts.length ? winners / allPnlPcts.length : 0}
              color="var(--positive)"
            />
            <Counter
              label="En perte"
              value={losers}
              ratio={allPnlPcts.length ? losers / allPnlPcts.length : 0}
              color="var(--negative)"
            />
            <Counter label="Investi" value={invested ? `${invested.toFixed(0)} €` : "—"} ratio={invested ? 1 : 0} />
            <Counter
              label="PnL latent"
              value={pnlKnown.length ? `${pnlTotal >= 0 ? "+" : ""}${pnlTotal.toFixed(0)} €` : "—"}
              valueColor={pnlKnown.length ? pnlColor(pnlTotal) : undefined}
              ratio={pnlKnown.length && invested ? Math.min(1, Math.abs(pnlTotal) / invested) : 0}
              color={pnlTotal >= 0 ? "var(--positive)" : "var(--negative)"}
            />
          </div>
        </header>

        <div
          className="flex flex-wrap items-center gap-2.5 pt-2 text-[11px]"
          style={{ borderTop: "1px solid var(--hairline)", color: "var(--text-dim)" }}
        >
          <span>
            Portefeuilles créés depuis l'écran Paniers (cochez des décisions puis « Créer un portefeuille ») —
            enregistrés en base, partagés par tous les clients de l'API. PnL latent = positions encore ouvertes.
          </span>
        </div>

        {isError && (
          <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--negative)", color: "var(--negative)" }}>
            Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
          </div>
        )}

        {!isError && list.length === 0 && (
          <div className="gd-panel text-xs" style={{ color: "var(--text-dim)" }}>
            <span>
              Aucun portefeuille. Allez sur l'écran <strong>Paniers</strong>, cochez des décisions dans la colonne
              « Portefeuille » puis cliquez « Créer un portefeuille ».
            </span>
          </div>
        )}

        {(portfolios ?? []).map((portfolio) => (
          <section key={portfolio.id} aria-label={portfolio.name} className="gd-panel">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="display m-0 text-[15px] font-semibold">{portfolio.name}</h2>
                <button
                  onClick={() => askGeorge(portfolio.id)}
                  className="text-[11px] px-2.5 py-1 rounded-full border"
                  style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
                >
                  🎙 Demander à George pour répartir le budget du portefeuille
                </button>
                <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                  Créé le {new Date(portfolio.created_at).toLocaleDateString("fr-FR")}
                </span>
              </div>
              <button
                onClick={() => deletePortfolioMutation.mutate(portfolio.id)}
                className="text-[11px] px-2.5 py-1 rounded-full border"
                style={{ borderColor: "var(--negative)", color: "var(--negative)" }}
              >
                Supprimer le portefeuille
              </button>
            </div>
            {portfolio.decisions.length === 0 ? (
              <div className="text-xs mb-2" style={{ color: "var(--text-dim)" }}>
                Ce portefeuille est vide.
              </div>
            ) : (
              <div className="rounded-lg overflow-hidden border" style={{ borderColor: "var(--hairline)" }}>
                <div className="overflow-x-auto gd-scrollbar">
                  <table className="w-full text-xs" style={{ borderCollapse: "collapse", minWidth: 840 }}>
                    <thead>
                      <tr style={{ background: "var(--panel-alt)", color: "var(--text-dim)" }}>
                        {["Ticker", "Entrée", "Prix", "Take-profit", "Stop-loss", "PnL", "Quantité", "Date", "Heure", ""].map((h) => (
                          <th
                            key={h}
                            className="text-left px-3 py-2 font-normal border-b"
                            style={{ borderColor: "var(--hairline)" }}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {portfolio.decisions.map((d, i) => (
                        <tr key={d.id} style={{ background: i % 2 === 0 ? "var(--bg)" : "var(--panel)" }}>
                          <td className="px-3 py-2">
                            <span className="mono font-bold" style={{ color: decisionColor(d.decision_type) }}>
                              {d.symbol}
                            </span>
                          </td>
                          <td className="px-3 py-2">{d.entry_price.toFixed(2)} €</td>
                          <td className="px-3 py-2 mono">{d.current_price != null ? `${d.current_price.toFixed(2)} €` : "—"}</td>
                          <td className="px-3 py-2">
                            {d.take_profit != null ? `${d.take_profit.toFixed(2)} €` : "—"}
                          </td>
                          <td className="px-3 py-2">{d.stop_loss != null ? `${d.stop_loss.toFixed(2)} €` : "—"}</td>
                          <td className="px-3 py-2 font-bold" style={{ color: pnlColor(d.pnl_pct) }}>
                            {formatPnlPct(d.pnl_pct)}
                          </td>
                          <td className="px-3 py-2 mono">{d.quantity ?? "—"}</td>
                          <td className="px-3 py-2">
                            {d.price_updated_at ? new Date(d.price_updated_at).toLocaleDateString("fr-FR") : "—"}
                          </td>
                          <td className="px-3 py-2 mono">
                            {d.price_updated_at
                              ? new Date(d.price_updated_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
                              : "—"}
                          </td>
                          <td className="px-3 py-2">
                            <button
                              onClick={() =>
                                removeDecisionMutation.mutate({ portfolioId: portfolio.id, decisionId: d.id })
                              }
                              className="text-[11px] px-2.5 py-1 rounded-full border"
                              style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
                            >
                              Retirer
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div
                  className="flex items-center justify-between px-3 py-2 text-xs border-t"
                  style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)" }}
                >
                  <span style={{ color: "var(--text-dim)" }}>PnL du portefeuille</span>
                  {portfolio.total_pnl_amount == null ? (
                    <span style={{ color: "var(--text-dim)" }}>
                      Renseignez des quantités (« Demander à George ») pour calculer le PnL total.
                    </span>
                  ) : (
                    <span className="font-bold mono" style={{ color: pnlColor(portfolio.total_pnl_amount) }}>
                      {formatAmount(portfolio.total_pnl_amount)}
                      {portfolio.total_invested ? ` (${formatPnlPct((portfolio.total_pnl_amount / portfolio.total_invested) * 100)})` : ""}
                    </span>
                  )}
                </div>
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
