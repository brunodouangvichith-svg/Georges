import { useEnergyPrices } from "../api/queries";

// Écran « Marché d'énergie » : dernier cours connu et variation sur 24 h,
// issus de l'import quotidien (GET /energy-prices).

const ENERGY_LABELS = {
  BRENT_CRUDE_USD: "Brent",
  WTI_USD: "WTI",
  NATURAL_GAS_USD: "Gaz naturel",
  DIESEL_USD: "Diesel",
  HEATING_OIL_USD: "Fioul domestique",
  GASOLINE_USD: "Essence",
};
const ENERGY_ORDER = Object.keys(ENERGY_LABELS);

function Message({ children }) {
  return (
    <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
      {children}
    </div>
  );
}

export default function Energie() {
  const { data, isLoading, isError } = useEnergyPrices();
  const prices = ENERGY_ORDER.map((code) => data?.find((e) => e.commodity_code === code)).filter(Boolean);

  return (
    <div className="h-full overflow-y-auto gd-scrollbar">
      <div className="mx-auto flex flex-col gap-4 px-5 py-4" style={{ maxWidth: 720 }}>
        <h1 className="display m-0 text-[18px] font-semibold">Marché d'énergie</h1>
        <section aria-label="Cours de l'énergie" className="gd-panel">
          {isLoading ? (
            <Message>Chargement des cours…</Message>
          ) : isError ? (
            <div role="alert" className="text-[12.5px]" style={{ color: "var(--negative)" }}>
              Impossible de contacter l'API — le serveur met parfois 1 à 2 minutes à répondre après une pause.
            </div>
          ) : prices.length === 0 ? (
            <Message>Aucune donnée pour l'instant (import quotidien pas encore passé).</Message>
          ) : (
            <div className="grid gap-x-4 gap-y-2 text-[13px]" style={{ gridTemplateColumns: "minmax(0, 1fr) auto auto" }}>
              {prices.map((e) => {
                const up = (e.change_24h_pct ?? 0) >= 0;
                return (
                  <div key={e.commodity_code} className="contents">
                    <span style={{ color: "var(--text-dim)" }}>{ENERGY_LABELS[e.commodity_code]}</span>
                    <span className="mono text-right">
                      {e.price.toFixed(2)} {e.currency}
                    </span>
                    <span className="mono text-right font-semibold" style={{ color: up ? "var(--positive)" : "var(--negative)" }}>
                      <span aria-hidden="true">{up ? "▲" : "▼"}</span>
                      <span className="sr-only">{up ? "en hausse" : "en baisse"}</span>
                      {e.change_24h_pct != null ? ` ${Math.abs(e.change_24h_pct).toFixed(2)} %` : ""}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
