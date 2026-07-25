import React, { useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Eye, PlusCircle, Wallet } from "lucide-react";

const palette = {
  ink: "#0a0e12",
  panel: "#12181f",
  panelAlt: "#171f28",
  hairline: "#232c35",
  amber: "#ffb020",
  amberDim: "#8a6a2e",
  green: "#3ddc84",
  greenDim: "#1f6e46",
  red: "#ff5c5c",
  redDim: "#7a3232",
  slate: "#8b95a1",
  bone: "#e8ecef",
};

const positions = [
  { t: "NVDA", name: "NVIDIA", country: "US", ccy: "USD", basket: "IA / Semi-conducteurs", weight: 8, pattern: "Bull Flag", conf: 82, dec: "Achat" },
  { t: "AMD", name: "Advanced Micro Devices", country: "US", ccy: "USD", basket: "IA / Semi-conducteurs", weight: 5, pattern: "Ascending Triangle", conf: 74, dec: "Achat" },
  { t: "ASML", name: "ASML Holding", country: "NL", ccy: "EUR", basket: "Semi-conducteurs", weight: 6, pattern: "Cup & Handle", conf: 78, dec: "Achat" },
  { t: "TSM", name: "TSMC (ADR)", country: "TW", ccy: "USD", basket: "Semi-conducteurs", weight: 6, pattern: "Breakout", conf: 80, dec: "Renforcer" },
  { t: "MSFT", name: "Microsoft", country: "US", ccy: "USD", basket: "Technologie / IA", weight: 6, pattern: "Bull Flag", conf: 71, dec: "Achat" },
  { t: "GOOGL", name: "Alphabet", country: "US", ccy: "USD", basket: "Technologie / IA", weight: 4, pattern: "Ascending Triangle", conf: 69, dec: "Surveiller" },
  { t: "CRWD", name: "CrowdStrike", country: "US", ccy: "USD", basket: "Cybersécurité", weight: 5, pattern: "Inverse H&S", conf: 76, dec: "Achat" },
  { t: "PANW", name: "Palo Alto Networks", country: "US", ccy: "USD", basket: "Cybersécurité", weight: 4, pattern: "Bull Flag", conf: 70, dec: "Achat" },
  { t: "NEE", name: "NextEra Energy", country: "US", ccy: "USD", basket: "Énergies renouvelables", weight: 3, pattern: "Falling Wedge", conf: 65, dec: "Surveiller" },
  { t: "SU.PA", name: "Schneider Electric", country: "FR", ccy: "EUR", basket: "Industrie / Énergie", weight: 4, pattern: "Ascending Triangle", conf: 72, dec: "Achat" },
  { t: "NVO", name: "Novo Nordisk (ADR)", country: "DK", ccy: "USD", basket: "Santé", weight: 4, pattern: "Double Bottom", conf: 68, dec: "Surveiller" },
  { t: "UNH", name: "UnitedHealth Group", country: "US", ccy: "USD", basket: "Santé", weight: 2, pattern: "Double Bottom", conf: 60, dec: "Surveiller" },
  { t: "JPM", name: "JPMorgan Chase", country: "US", ccy: "USD", basket: "Finance", weight: 5, pattern: "Bull Flag", conf: 73, dec: "Achat" },
  { t: "BNP", name: "BNP Paribas", country: "FR", ccy: "EUR", basket: "Finance", weight: 3, pattern: "Ascending Triangle", conf: 66, dec: "Surveiller" },
  { t: "SIE.DE", name: "Siemens", country: "DE", ccy: "EUR", basket: "Industrie", weight: 4, pattern: "Cup & Handle", conf: 70, dec: "Achat" },
  { t: "7203.T", name: "Toyota Motor", country: "JP", ccy: "JPY", basket: "Industrie / Auto", weight: 3, pattern: "Falling Wedge", conf: 63, dec: "Surveiller" },
  { t: "MC.PA", name: "LVMH", country: "FR", ccy: "EUR", basket: "Consommation / Luxe", weight: 2, pattern: "Double Bottom", conf: 58, dec: "Surveiller" },
  { t: "OR.PA", name: "L'Oréal", country: "FR", ccy: "EUR", basket: "Consommation", weight: 3, pattern: "Ascending Triangle", conf: 67, dec: "Achat" },
  { t: "INFY", name: "Infosys (ADR)", country: "IN", ccy: "USD", basket: "Inde / Services IT", weight: 4, pattern: "Bull Flag", conf: 71, dec: "Achat" },
  { t: "SONY", name: "Sony Group (ADR)", country: "JP", ccy: "USD", basket: "Japon / Technologie", weight: 4, pattern: "Breakout", conf: 75, dec: "Achat" },
];

const CAPITAL = 1000000;
const investedPct = positions.reduce((s, p) => s + p.weight, 0);
const cashPct = 100 - investedPct;

const georgeIndex = [
  { basket: "IA & Semi-conducteurs", score: 84 },
  { basket: "Cybersécurité", score: 78 },
  { basket: "Technologie / IA (mega-cap)", score: 74 },
  { basket: "Inde / Services IT", score: 73 },
  { basket: "Japon / Technologie", score: 71 },
  { basket: "Industrie / Énergie", score: 70 },
  { basket: "Finance", score: 69 },
  { basket: "Santé", score: 62 },
  { basket: "Consommation / Luxe", score: 55 },
];

const decisionColor = (d) => (d === "Achat" || d === "Renforcer" ? palette.green : d === "Surveiller" ? palette.amber : palette.red);
const decisionIcon = (d) => (d === "Achat" || d === "Renforcer" ? TrendingUp : Eye);
const scoreColor = (s) => (s >= 75 ? palette.green : s >= 65 ? palette.amber : palette.red);

const sectorAgg = (() => {
  const map = {};
  positions.forEach((p) => { map[p.basket] = (map[p.basket] || 0) + p.weight; });
  map["Trésorerie"] = cashPct;
  return Object.entries(map).map(([name, value]) => ({ name, value }));
})();

const PIE_COLORS = ["#ffb020", "#3ddc84", "#5aa9ff", "#ff5c5c", "#c58aff", "#4fd6c5", "#e0975a", "#8b95a1", "#e85d9a", "#7fd6ff"];

const FILTERS = ["Tous", "Achat", "Renforcer", "Surveiller"];

export default function GeorgeDashboard() {
  const [filter, setFilter] = useState("Tous");

  const filtered = useMemo(
    () => (filter === "Tous" ? positions : positions.filter((p) => p.dec === filter)),
    [filter]
  );

  const counts = useMemo(() => {
    const c = { Achat: 0, Renforcer: 0, Surveiller: 0 };
    positions.forEach((p) => { c[p.dec] = (c[p.dec] || 0) + 1; });
    return c;
  }, []);

  const avgConf = Math.round(positions.reduce((s, p) => s + p.conf, 0) / positions.length);

  return (
    <div style={{ background: palette.ink, minHeight: "100vh", fontFamily: "'IBM Plex Mono', 'JetBrains Mono', monospace", color: palette.bone }} className="w-full">
      <style>{`
        @keyframes ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
        .ticker-track { animation: ticker-scroll 38s linear infinite; }
        @media (prefers-reduced-motion: reduce) { .ticker-track { animation: none; } }
        .gd-scrollbar::-webkit-scrollbar { height: 6px; width: 6px; }
        .gd-scrollbar::-webkit-scrollbar-thumb { background: ${palette.hairline}; border-radius: 3px; }
      `}</style>

      {/* Ticker tape */}
      <div style={{ borderBottom: `1px solid ${palette.hairline}`, background: palette.panel, overflow: "hidden" }} className="w-full py-2">
        <div className="ticker-track flex whitespace-nowrap" style={{ width: "200%" }}>
          {[...positions, ...positions].map((p, i) => (
            <span key={i} className="inline-flex items-center gap-2 px-4 text-xs" style={{ color: palette.slate }}>
              <span style={{ color: palette.bone, fontWeight: 700 }}>{p.t}</span>
              <span>{p.pattern}</span>
              <span style={{ color: decisionColor(p.dec), fontWeight: 700 }}>{p.conf}%</span>
              <span style={{ color: palette.hairline }}>│</span>
            </span>
          ))}
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-5 py-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
          <div>
            <div className="text-xs tracking-widest" style={{ color: palette.amber, letterSpacing: "0.2em" }}>GEORGE · TERMINAL D'ANALYSE</div>
            <h1 className="text-2xl sm:text-3xl font-bold mt-1" style={{ color: palette.bone }}>Portefeuille de test — 1 000 000 €</h1>
            <div className="text-xs mt-1" style={{ color: palette.slate }}>Simulation illustrative · patterns et confiances non issus d'un flux de marché réel</div>
          </div>
          <div className="flex gap-3 text-xs">
            <div className="px-3 py-2 rounded" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
              <div style={{ color: palette.slate }}>Investi</div>
              <div style={{ color: palette.green, fontWeight: 700, fontSize: 15 }}>{investedPct}%</div>
            </div>
            <div className="px-3 py-2 rounded" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
              <div style={{ color: palette.slate }}>Confiance moy.</div>
              <div style={{ color: palette.amber, fontWeight: 700, fontSize: 15 }}>{avgConf}%</div>
            </div>
            <div className="px-3 py-2 rounded" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
              <div style={{ color: palette.slate }}>Lignes</div>
              <div style={{ color: palette.bone, fontWeight: 700, fontSize: 15 }}>{positions.length}</div>
            </div>
          </div>
        </div>

        {/* Decision summary strip */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded p-3 flex items-center gap-3" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
            <TrendingUp size={18} color={palette.green} />
            <div>
              <div className="text-xs" style={{ color: palette.slate }}>Achat / Renforcer</div>
              <div style={{ color: palette.green, fontWeight: 700 }}>{counts.Achat + counts.Renforcer} positions</div>
            </div>
          </div>
          <div className="rounded p-3 flex items-center gap-3" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
            <Eye size={18} color={palette.amber} />
            <div>
              <div className="text-xs" style={{ color: palette.slate }}>Surveiller</div>
              <div style={{ color: palette.amber, fontWeight: 700 }}>{counts.Surveiller} positions</div>
            </div>
          </div>
          <div className="rounded p-3 flex items-center gap-3" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
            <Wallet size={18} color={palette.slate} />
            <div>
              <div className="text-xs" style={{ color: palette.slate }}>Réserve de cash</div>
              <div style={{ color: palette.bone, fontWeight: 700 }}>{cashPct}% · {(CAPITAL * cashPct / 100).toLocaleString("fr-FR")} €</div>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-5 gap-5 mb-6">
          {/* George Index gauges */}
          <div className="lg:col-span-2 rounded p-4" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
            <div className="text-xs mb-3" style={{ color: palette.amber, letterSpacing: "0.1em" }}>GEORGE INDEX PAR PANIER</div>
            <div className="space-y-3">
              {georgeIndex.map((g) => (
                <div key={g.basket}>
                  <div className="flex justify-between text-xs mb-1">
                    <span style={{ color: palette.bone }}>{g.basket}</span>
                    <span style={{ color: scoreColor(g.score), fontWeight: 700 }}>{g.score}</span>
                  </div>
                  <div style={{ background: palette.panelAlt, height: 6, borderRadius: 3 }}>
                    <div style={{ width: `${g.score}%`, background: scoreColor(g.score), height: 6, borderRadius: 3 }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Allocation donut */}
          <div className="lg:col-span-3 rounded p-4" style={{ background: palette.panel, border: `1px solid ${palette.hairline}` }}>
            <div className="text-xs mb-1" style={{ color: palette.amber, letterSpacing: "0.1em" }}>ALLOCATION PAR PANIER</div>
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sectorAgg} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={1}>
                    {sectorAgg.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke={palette.panel} />)}
                  </Pie>
                  <Tooltip
                    formatter={(v, n) => [`${v}%`, n]}
                    contentStyle={{ background: palette.panelAlt, border: `1px solid ${palette.hairline}`, borderRadius: 6, fontSize: 12, color: palette.bone }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {sectorAgg.map((s, i) => (
                <div key={s.name} className="flex items-center gap-1 text-xs" style={{ color: palette.slate }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: PIE_COLORS[i % PIE_COLORS.length], display: "inline-block" }} />
                  {s.name} · {s.value}%
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-2 mb-3">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="text-xs px-3 py-1.5 rounded"
              style={{
                background: filter === f ? palette.amber : palette.panel,
                color: filter === f ? palette.ink : palette.slate,
                border: `1px solid ${filter === f ? palette.amber : palette.hairline}`,
                fontWeight: filter === f ? 700 : 400,
              }}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Positions table */}
        <div className="rounded overflow-hidden" style={{ border: `1px solid ${palette.hairline}` }}>
          <div className="overflow-x-auto gd-scrollbar">
            <table className="w-full text-xs" style={{ borderCollapse: "collapse", minWidth: 680 }}>
              <thead>
                <tr style={{ background: palette.panelAlt, color: palette.slate }}>
                  {["Ticker", "Société", "Panier", "Poids", "Montant", "Pattern", "Confiance", "Décision"].map((h) => (
                    <th key={h} className="text-left px-3 py-2 font-normal" style={{ borderBottom: `1px solid ${palette.hairline}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((p, i) => {
                  const Icon = decisionIcon(p.dec);
                  return (
                    <tr key={p.t} style={{ background: i % 2 === 0 ? palette.ink : palette.panel }}>
                      <td className="px-3 py-2 font-bold" style={{ color: palette.bone }}>{p.t}</td>
                      <td className="px-3 py-2" style={{ color: palette.slate }}>{p.name}</td>
                      <td className="px-3 py-2" style={{ color: palette.slate }}>{p.basket}</td>
                      <td className="px-3 py-2">{p.weight}%</td>
                      <td className="px-3 py-2">{(CAPITAL * p.weight / 100).toLocaleString("fr-FR")} €</td>
                      <td className="px-3 py-2" style={{ color: palette.slate }}>{p.pattern}</td>
                      <td className="px-3 py-2 font-bold" style={{ color: scoreColor(p.conf) }}>{p.conf}%</td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1 font-bold" style={{ color: decisionColor(p.dec) }}>
                          <Icon size={12} /> {p.dec}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="text-xs mt-5 pb-6" style={{ color: palette.slate }}>
          Document de démonstration. Portefeuille, patterns et scores fictifs — ne constitue pas un conseil en investissement.
        </div>
      </div>
    </div>
  );
}
