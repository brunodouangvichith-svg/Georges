import { useMemo, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingUp, Eye, Wallet } from "lucide-react";
import { positions, georgeIndex, CAPITAL, decisionColor, scoreColor } from "../data";

const PIE_COLORS = ["#ffb020", "#3ddc84", "#5aa9ff", "#ff5c5c", "#c58aff", "#4fd6c5", "#e0975a", "#8b95a1", "#e85d9a", "#7fd6ff"];
const FILTERS = ["Tous", "Achat", "Renforcer", "Surveiller"];

export default function Paniers() {
  const [filter, setFilter] = useState("Tous");

  const investedPct = positions.reduce((s, p) => s + p.weight, 0);
  const cashPct = 100 - investedPct;

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

  const sectorAgg = useMemo(() => {
    const map = {};
    positions.forEach((p) => { map[p.basket] = (map[p.basket] || 0) + p.weight; });
    map["Trésorerie"] = cashPct;
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [cashPct]);

  return (
    <div className="h-full overflow-y-auto gd-scrollbar px-5 py-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
          <div>
            <div className="text-xs tracking-widest" style={{ color: "var(--warning)", letterSpacing: "0.2em" }}>
              GEORGE · PANIERS
            </div>
            <h1 className="display text-2xl sm:text-3xl font-bold mt-1">Portefeuille de test — 1 000 000 €</h1>
            <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>
              Simulation illustrative · patterns et confiances non issus d'un flux de marché réel
            </div>
          </div>
          <div className="flex gap-3 text-xs">
            {[
              ["Investi", `${investedPct}%`, "var(--positive)"],
              ["Confiance moy.", `${avgConf}%`, "var(--warning)"],
              ["Lignes", positions.length, "var(--text)"],
            ].map(([label, value, color]) => (
              <div key={label} className="px-3 py-2 rounded-lg border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
                <div style={{ color: "var(--text-dim)" }}>{label}</div>
                <div className="font-bold text-[15px]" style={{ color }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg p-3 flex items-center gap-3 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <TrendingUp size={18} color="var(--positive)" />
            <div>
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>Achat / Renforcer</div>
              <div className="font-bold" style={{ color: "var(--positive)" }}>{counts.Achat + counts.Renforcer} positions</div>
            </div>
          </div>
          <div className="rounded-lg p-3 flex items-center gap-3 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <Eye size={18} color="var(--warning)" />
            <div>
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>Surveiller</div>
              <div className="font-bold" style={{ color: "var(--warning)" }}>{counts.Surveiller} positions</div>
            </div>
          </div>
          <div className="rounded-lg p-3 flex items-center gap-3 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <Wallet size={18} color="var(--text-dim)" />
            <div>
              <div className="text-xs" style={{ color: "var(--text-dim)" }}>Réserve de cash</div>
              <div className="font-bold">{cashPct}% · {(CAPITAL * cashPct / 100).toLocaleString("fr-FR")} €</div>
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-5 gap-5 mb-6">
          <div className="lg:col-span-2 rounded-lg p-4 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <div className="text-xs mb-3 tracking-wider" style={{ color: "var(--warning)" }}>GEORGE INDEX PAR PANIER</div>
            <div className="space-y-3">
              {georgeIndex.map((g) => (
                <div key={g.basket}>
                  <div className="flex justify-between text-xs mb-1">
                    <span>{g.basket}</span>
                    <span className="font-bold" style={{ color: scoreColor(g.score) }}>{g.score}</span>
                  </div>
                  <div className="rounded-full h-1.5" style={{ background: "var(--panel-alt)" }}>
                    <div className="rounded-full h-1.5" style={{ width: `${g.score}%`, background: scoreColor(g.score) }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-3 rounded-lg p-4 border" style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}>
            <div className="text-xs mb-1 tracking-wider" style={{ color: "var(--warning)" }}>ALLOCATION PAR PANIER</div>
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sectorAgg} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={1}>
                    {sectorAgg.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="var(--panel)" />)}
                  </Pie>
                  <Tooltip
                    formatter={(v, n) => [`${v}%`, n]}
                    contentStyle={{ background: "var(--panel-alt)", border: "1px solid var(--hairline)", borderRadius: 6, fontSize: 12, color: "var(--text)" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
              {sectorAgg.map((s, i) => (
                <div key={s.name} className="flex items-center gap-1 text-xs" style={{ color: "var(--text-dim)" }}>
                  <span className="inline-block w-2 h-2 rounded-sm" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  {s.name} · {s.value}%
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-2 mb-3">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="text-xs px-3 py-1.5 rounded-md border"
              style={{
                background: filter === f ? "var(--warning)" : "var(--panel)",
                color: filter === f ? "#1a1305" : "var(--text-dim)",
                borderColor: filter === f ? "var(--warning)" : "var(--hairline)",
                fontWeight: filter === f ? 700 : 400,
              }}
            >
              {f}
            </button>
          ))}
        </div>

        <div className="rounded-lg overflow-hidden border" style={{ borderColor: "var(--hairline)" }}>
          <div className="overflow-x-auto gd-scrollbar">
            <table className="w-full text-xs" style={{ borderCollapse: "collapse", minWidth: 680 }}>
              <thead>
                <tr style={{ background: "var(--panel-alt)", color: "var(--text-dim)" }}>
                  {["Ticker", "Société", "Panier", "Poids", "Montant", "Pattern", "Confiance", "Décision"].map((h) => (
                    <th key={h} className="text-left px-3 py-2 font-normal border-b" style={{ borderColor: "var(--hairline)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((p, i) => {
                  const Icon = p.dec === "Achat" || p.dec === "Renforcer" ? TrendingUp : Eye;
                  return (
                    <tr key={p.t} style={{ background: i % 2 === 0 ? "var(--bg)" : "var(--panel)" }}>
                      <td className="px-3 py-2 font-bold">{p.t}</td>
                      <td className="px-3 py-2" style={{ color: "var(--text-dim)" }}>{p.n}</td>
                      <td className="px-3 py-2" style={{ color: "var(--text-dim)" }}>{p.basket}</td>
                      <td className="px-3 py-2">{p.weight}%</td>
                      <td className="px-3 py-2">{(CAPITAL * p.weight / 100).toLocaleString("fr-FR")} €</td>
                      <td className="px-3 py-2" style={{ color: "var(--text-dim)" }}>{p.pattern}</td>
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

        <div className="text-xs mt-5 pb-6" style={{ color: "var(--text-dim)" }}>
          Document de démonstration. Portefeuille, patterns et scores fictifs — ne constitue pas un conseil en investissement.
        </div>
      </div>
    </div>
  );
}
