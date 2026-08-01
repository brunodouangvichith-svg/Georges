import { useState } from "react";
import CandlestickChart from "../components/CandlestickChart";
import ResponsePopup from "../components/ResponsePopup";
import { useCarryTrade, useCarryTradeDetail, useExplainCarryTrade, useRefreshCarryTrade } from "../api/queries";
import { decisionColor } from "../data";

function EmptyState({ children }) {
  return (
    <div className="text-[13px] p-4 rounded-lg border" style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}>
      {children}
    </div>
  );
}

function crowdingColor(score) {
  if (score == null) return "var(--text-dim)";
  return score >= 75 ? "var(--negative)" : score >= 60 ? "var(--warning)" : "var(--positive)";
}

function fmtPct(v) {
  return v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export default function CarryTrade() {
  const { data: pairs, isLoading, isError } = useCarryTrade();
  const [selected, setSelected] = useState(null);
  const [popup, setPopup] = useState(null);
  const refreshMutation = useRefreshCarryTrade();

  const sorted = [...(pairs ?? [])].sort((a, b) => (b.carry_vol_ratio ?? -Infinity) - (a.carry_vol_ratio ?? -Infinity));
  const selectedSymbol = selected ?? sorted[0]?.symbol ?? null;

  const { data: detail } = useCarryTradeDetail(selectedSymbol);
  const explainMutation = useExplainCarryTrade();

  function refreshData() {
    setPopup({
      title: "Rafraîchissement Carry Trade",
      status: "loading",
      text: null,
      loadingText: "Téléchargement des cours FX, des taux et du positionnement COT en cours…",
    });
    refreshMutation.mutate(undefined, {
      onSuccess: (data) =>
        setPopup({
          title: "Rafraîchissement Carry Trade",
          status: "done",
          text: `${data.fx_prices_updated} paires, ${data.rates_updated.length} taux, ${data.cot_updated.length} positions COT mis à jour.`,
        }),
      onError: (err) => setPopup({ title: "Rafraîchissement Carry Trade", status: "error", text: err.message }),
    });
  }

  function askExplanation() {
    const title = `George explique — ${selectedSymbol}`;
    setPopup({ title, status: "loading", text: null, loadingText: "George réfléchit…" });
    explainMutation.mutate(selectedSymbol, {
      onSuccess: (data) => setPopup({ title, status: "done", text: data.explanation }),
      onError: (err) => setPopup({ title, status: "error", text: err.message }),
    });
  }

  return (
    <>
      <ResponsePopup popup={popup} onClose={() => setPopup(null)} />
      <div className="grid h-full overflow-hidden" style={{ gridTemplateColumns: "1fr 350px" }}>
        <div className="overflow-y-auto px-4.5 py-4 gd-scrollbar">
          <div className="flex items-center justify-between mb-3.5">
            <div>
              <div className="display text-[16px] font-semibold">Panier Carry Trade — paires devises</div>
              <div className="text-xs mt-0.5 max-w-[520px]" style={{ color: "var(--text-dim)" }}>
                Classées par ratio carry/volatilité. Le positionnement (COT) mesure le degré de saturation de la
                position vendeuse sur la devise de financement — plus la barre est pleine, plus George juge le trade
                surpeuplé, avec un risque de dénouement brutal ("unwind") en cas de resserrement inattendu.
              </div>
            </div>
            <button
              onClick={refreshData}
              disabled={refreshMutation.isPending}
              className="text-[11.5px] px-3 py-1.5 rounded-full border whitespace-nowrap"
              style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
            >
              {refreshMutation.isPending ? "Rafraîchissement…" : "🔄 Rafraîchir"}
            </button>
          </div>

          {isError && (
            <EmptyState>
              Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
            </EmptyState>
          )}
          {!isError && !isLoading && sorted.length === 0 && (
            <EmptyState>
              Aucune paire en base. Lancez <code>python -m ingestion.carry_pairs</code> puis{" "}
              <code>python -m ingestion.fx_rates</code>, <code>python -m ingestion.carry_rates</code> et{" "}
              <code>python -m ingestion.cot_positioning</code>.
            </EmptyState>
          )}
          {!isError && sorted.length > 0 && (
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  {["Paire", "Financement", "Cible", "Différentiel", "Carry annualisé", "Vol. réalisée", "Carry/Vol", "Positionnement (COT)", "Décision"].map(
                    (h) => (
                      <th
                        key={h}
                        className="text-left text-[10.5px] uppercase tracking-wider font-medium px-2.5 py-2 border-b"
                        style={{ color: "var(--text-dim)", borderColor: "var(--hairline)" }}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => (
                  <tr
                    key={p.symbol}
                    onClick={() => setSelected(p.symbol)}
                    className="cursor-pointer"
                    style={{ background: p.symbol === selectedSymbol ? "var(--panel-alt)" : "transparent" }}
                  >
                    <td className="px-2.5 py-2 mono font-semibold">{p.symbol.replace("=X", "")}</td>
                    <td className="px-2.5 py-2">
                      {p.funding_currency}{" "}
                      <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                        {p.funding_rate_pct != null ? `${p.funding_rate_pct}%` : "—"}
                      </span>
                    </td>
                    <td className="px-2.5 py-2">
                      {p.target_currency}{" "}
                      <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                        {p.target_rate_pct != null ? `${p.target_rate_pct}%` : "—"}
                      </span>
                    </td>
                    <td className="px-2.5 py-2 mono">{p.carry_pct != null ? `+${p.carry_pct} pts` : "—"}</td>
                    <td className="px-2.5 py-2 mono font-semibold" style={{ color: decisionColor(p.decision) }}>
                      {fmtPct(p.carry_pct)}
                    </td>
                    <td className="px-2.5 py-2">{p.realized_vol_pct != null ? `${p.realized_vol_pct}%` : "—"}</td>
                    <td className="px-2.5 py-2 mono">{p.carry_vol_ratio ?? "—"}</td>
                    <td className="px-2.5 py-2">
                      <span
                        className="inline-block w-[60px] h-[5px] rounded-full align-middle mr-1.5"
                        style={{ background: "var(--panel-alt)" }}
                      >
                        <span
                          className="block h-full rounded-full"
                          style={{
                            width: `${p.cot_crowding_score ?? 0}%`,
                            background: crowdingColor(p.cot_crowding_score),
                          }}
                        />
                      </span>
                      <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
                        {p.cot_crowding_score != null ? `${p.cot_crowding_score}%` : "—"}
                      </span>
                    </td>
                    <td className="px-2.5 py-2">
                      <span
                        className="text-[10.5px] font-semibold px-2 py-0.5 rounded-md"
                        style={{ background: "var(--panel-alt)", color: decisionColor(p.decision) }}
                      >
                        {p.decision}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail panel */}
        <div className="border-l overflow-y-auto flex flex-col" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
          {!detail ? (
            <div className="p-5 text-[13px]" style={{ color: "var(--text-dim)" }}>
              Sélectionnez une paire dans la liste.
            </div>
          ) : (
            <div className="px-5 pt-5 pb-5">
              <h2 className="display text-[19px] font-semibold mb-0.5">{detail.symbol.replace("=X", "")}</h2>
              <div className="text-[12.5px] mb-4" style={{ color: "var(--text-dim)" }}>
                {detail.name}
              </div>

              <div className="border rounded-[10px] mb-4 overflow-hidden flex justify-center" style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)" }}>
                <CandlestickChart candles={detail.recent_prices} width={290} height={130} />
              </div>

              <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                Paramètres du carry
              </div>
              {[
                ["Taux financement", detail.funding_rate_pct != null ? `${detail.funding_rate_pct}%` : "—"],
                ["Taux cible", detail.target_rate_pct != null ? `${detail.target_rate_pct}%` : "—"],
                ["Différentiel", detail.carry_pct != null ? `+${detail.carry_pct} pts` : "—"],
                ["Volatilité réalisée", detail.realized_vol_pct != null ? `${detail.realized_vol_pct}%` : "—"],
                ["Ratio carry/vol", detail.carry_vol_ratio ?? "—"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between text-[13px] py-1.5 border-b" style={{ borderColor: "var(--hairline)" }}>
                  <span style={{ color: "var(--text-dim)" }}>{k}</span>
                  <span className="mono">{v}</span>
                </div>
              ))}

              <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>
                Positionnement spéculatif (CFTC)
              </div>
              <div className="mt-1.5">
                <div className="relative h-2 rounded" style={{ background: "linear-gradient(90deg, var(--positive), var(--warning) 60%, var(--negative) 75%)" }}>
                  {detail.cot_crowding_score != null && (
                    <div
                      className="absolute -top-1 w-0.5 h-4"
                      style={{ left: `${detail.cot_crowding_score}%`, background: "var(--text)" }}
                    />
                  )}
                </div>
                <div className="flex justify-between text-[10px] mt-1" style={{ color: "var(--text-dim)" }}>
                  <span>Neutre</span>
                  <span>Extrême (saturé)</span>
                </div>
              </div>

              {detail.cot_crowding_score != null && (
                <div
                  className="mt-3.5 p-2.5 rounded-lg text-[12px] leading-relaxed"
                  style={{
                    background: detail.cot_crowding_score >= 75 ? "rgba(226,85,95,.12)" : "rgba(47,191,130,.10)",
                    border: `1px solid ${detail.cot_crowding_score >= 75 ? "rgba(226,85,95,.35)" : "rgba(47,191,130,.3)"}`,
                    color: detail.cot_crowding_score >= 75 ? "var(--negative)" : "var(--positive)",
                  }}
                >
                  {detail.cot_crowding_score >= 75
                    ? `⚠ Positionnement extrême (${detail.cot_crowding_score}%) sur la devise de financement — risque de dénouement brutal en cas de resserrement inattendu.`
                    : `✓ Positionnement encore raisonnable (${detail.cot_crowding_score}%) sur la devise de financement.`}
                </div>
              )}

              <button
                className="mt-4 w-full py-2.5 rounded-lg font-semibold text-[13px]"
                style={{ background: "var(--accent)", color: "#fff" }}
                disabled={explainMutation.isPending}
                onClick={askExplanation}
              >
                {explainMutation.isPending ? "George réfléchit…" : "Demander une analyse à George"}
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
