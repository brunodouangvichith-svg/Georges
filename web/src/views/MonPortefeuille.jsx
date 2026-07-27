import { useDeletePortfolio, usePortfolios, useRemoveDecisionFromPortfolio } from "../api/queries";
import { decisionColor, scoreColor } from "../data";

export default function MonPortefeuille() {
  const { data: portfolios, isError } = usePortfolios();
  const deletePortfolioMutation = useDeletePortfolio();
  const removeDecisionMutation = useRemoveDecisionFromPortfolio();

  return (
    <div className="h-full overflow-y-auto gd-scrollbar px-5 py-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <div className="text-xs tracking-widest" style={{ color: "var(--warning)", letterSpacing: "0.2em" }}>
            GEORGE · MON PORTEFEUILLE
          </div>
          <h1 className="display text-2xl sm:text-3xl font-bold mt-1">Mon portefeuille</h1>
          <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>
            Portefeuilles créés depuis l'écran Paniers (cochez des décisions puis « Créer un portefeuille ») —
            enregistrés en base, partagés par tous les clients de l'API.
          </div>
        </div>

        {isError && (
          <div
            className="text-[13px] p-4 rounded-lg border mb-6"
            style={{ borderColor: "var(--negative)", color: "var(--negative)" }}
          >
            Impossible de contacter l'API — vérifiez qu'elle tourne (<code>uvicorn api.main:app --reload</code>).
          </div>
        )}

        {!isError && (portfolios ?? []).length === 0 && (
          <div className="text-xs" style={{ color: "var(--text-dim)" }}>
            Aucun portefeuille. Allez sur l'écran <strong>Paniers</strong>, cochez des décisions dans la colonne
            « Portefeuille » puis cliquez « Créer un portefeuille ».
          </div>
        )}

        {(portfolios ?? []).map((portfolio) => (
          <div key={portfolio.id} className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="display text-[15px] font-semibold">{portfolio.name}</h2>
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
                  <table className="w-full text-xs" style={{ borderCollapse: "collapse", minWidth: 680 }}>
                    <thead>
                      <tr style={{ background: "var(--panel-alt)", color: "var(--text-dim)" }}>
                        {["Ticker", "Décision", "Entrée", "Take-profit", "Stop-loss", "Confiance", ""].map((h) => (
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
                          <td className="px-3 py-2 font-bold">{d.symbol}</td>
                          <td className="px-3 py-2">
                            <span className="font-bold" style={{ color: decisionColor(d.decision_type) }}>
                              {d.decision_type}
                            </span>
                          </td>
                          <td className="px-3 py-2">{d.entry_price.toFixed(2)} €</td>
                          <td className="px-3 py-2">
                            {d.take_profit != null ? `${d.take_profit.toFixed(2)} €` : "—"}
                          </td>
                          <td className="px-3 py-2">{d.stop_loss != null ? `${d.stop_loss.toFixed(2)} €` : "—"}</td>
                          <td className="px-3 py-2 font-bold" style={{ color: scoreColor(d.confidence) }}>
                            {Math.round(d.confidence)}%
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
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
