import { useEffect, useState } from "react";
import { supabase } from "../api/supabaseClient";
import { marketStatus } from "../lib/marketStatus";
import InstallBar from "./InstallBar";

const NAV = [
  { key: "univers", label: "Univers", icon: "◆" },
  { key: "trading", label: "Trading", icon: "⇅" },
  { key: "energie", label: "Marché d'énergie", shortLabel: "Énergie", icon: "↯" },
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
    <div className="gd-shell">
      <header className="gd-header">
        <div className="display font-bold text-[19px] tracking-tight">
          George<span style={{ color: "var(--accent)" }}>.</span>
        </div>
        <nav className="gd-topnav" aria-label="Écrans">
          {NAV.map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              aria-current={view === item.key ? "page" : undefined}
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
            {market.reason && <span className="gd-desktop-only"> · {market.reason}</span>}
          </span>
          <span className="mono gd-desktop-only">{market.time} · Euronext Paris</span>
          <button
            onClick={() => supabase.auth.signOut()}
            className="gd-signout text-[11.5px] px-2.5 py-1 rounded-full border"
            style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
          >
            Se déconnecter
          </button>
        </div>
      </header>
      <InstallBar />
      {/* key : rejoue le fondu à chaque changement d'écran. */}
      <main key={view} className="gd-main">
        {children}
      </main>
      <nav className="gd-tabbar" aria-label="Écrans">
        {NAV.map((item) => (
          <button key={item.key} onClick={() => setView(item.key)} aria-current={view === item.key ? "page" : undefined}>
            <span aria-hidden="true" className="gd-tabbar-icon">
              {item.icon}
            </span>
            {item.shortLabel ?? item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
