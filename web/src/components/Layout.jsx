import { supabase } from "../api/supabaseClient";

const NAV = [
  { key: "univers", label: "Univers", icon: "◆" },
  { key: "paniers", label: "Paniers", icon: "▤" },
  { key: "portefeuille", label: "Mon Portefeuille", icon: "★" },
];

export default function Layout({ view, setView, children }) {
  return (
    <div className="grid h-screen" style={{ gridTemplateRows: "56px 1fr" }}>
      <div
        className="flex items-center gap-7 px-5 border-b"
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
          <span>
            <span
              className="inline-block w-[7px] h-[7px] rounded-full mr-1.5"
              style={{ background: "var(--positive)", boxShadow: "0 0 6px var(--positive)" }}
            />
            Marché ouvert
          </span>
          <span className="mono">08:30 · Euronext Paris</span>
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
