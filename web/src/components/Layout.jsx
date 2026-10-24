import { useEffect, useState } from "react";
import { supabase } from "../api/supabaseClient";
import { marketStatus } from "../lib/marketStatus";

const NAV = [
  { key: "univers", label: "Univers", icon: "◆" },
  { key: "trading", label: "Trading", icon: "⇅" },
  { key: "obligataire", label: "Obligataire", icon: "≈" },
  { key: "rapport", label: "Rapport", icon: "▤" },
];

// Recalcule le statut de séance toutes les 30 s (heure de Paris).
function useMarketStatus() {
  const [status, setStatus] = useState(() => marketStatus());
  useEffect(() => {
    const id = setInterval(() => setStatus(marketStatus()), 30_000);
    return () => clearInterval(id);
  }, []);
  return status;
}

export default function Layout({ view, setView, children }) {
  const market = useMarketStatus();
  return (
    <div
      className="grid h-screen"
      // minmax(0, 1fr) : la colonne ne s'élargit jamais au-delà de l'écran ;
      // sur téléphone, c'est la barre du haut qui défile horizontalement.
      style={{ gridTemplateRows: "56px 1fr", gridTemplateColumns: "minmax(0, 1fr)", background: "var(--bg)", color: "var(--text)" }}
    >
      <div
        className="flex items-center gap-7 px-5 border-b overflow-x-auto whitespace-nowrap"
        style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}
      >
        <div className="display font-bold text-[19px] tracking-tight">
          George<span style={{ color: "var(--accent)" }}>.</span>
        </div>
        <nav className="flex gap-1">
          {NAV.map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              className="text-sm font-medium px-3.5 py-2 rounded-lg transition-colors"
              style={{
                color: view === item.key ? "var(--text)" : "var(--text-dim)",
                background: view === item.key ? "var(--panel-alt)" : "transparent",
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-xs" style={{ color: "var(--text-dim)" }}>
          <span title={market.reason ? `Euronext Paris : ${market.reason}` : "Séance continue 09:00-17:30"}>
            <span
              className="inline-block w-[7px] h-[7px] rounded-full mr-1.5"
              style={{
                background: market.open ? "var(--positive)" : "var(--negative)",
                boxShadow: market.open ? "0 0 6px var(--positive)" : "none",
              }}
            />
            {market.label}
            {market.reason && <span> · {market.reason}</span>}
          </span>
          <span className="mono">{market.time} · Euronext Paris</span>
          <button
            onClick={() => supabase.auth.signOut()}
            className="text-[11.5px] px-2.5 py-1 rounded-full border"
            style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
          >
            Se déconnecter
          </button>
        </div>
      </div>
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}
