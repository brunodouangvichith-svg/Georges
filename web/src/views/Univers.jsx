import { useState } from "react";
import Sparkline from "../components/Sparkline";
import Gauge from "../components/Gauge";
import CandlestickChart from "../components/CandlestickChart";
import { positions, georgeIndex, macro, agentEvents, decisionColor, scoreColor } from "../data";

const FILTERS = ["Tous", "Achat", "Surveiller", "Alléger"];

const SIDEBAR_NAV = [
  { icon: "◆", label: "Univers", active: true },
  { icon: "▤", label: "Paniers" },
  { icon: "✓", label: "Décisions" },
  { icon: "◔", label: "George Index" },
  { icon: "⏱", label: "Historique" },
];

function tagStyle(dec) {
  const color = decisionColor(dec);
  return {
    color,
    background: `color-mix(in srgb, ${color} 15%, transparent)`,
  };
}

export default function Univers() {
  const [filter, setFilter] = useState("Tous");
  const [selected, setSelected] = useState(positions[0].t);
  const [dockMsg, setDockMsg] = useState(null);

  const filtered = filter === "Tous" ? positions : positions.filter((p) => p.dec === filter);
  const current = positions.find((p) => p.t === selected) ?? positions[0];

  return (
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
              <div className="display text-[16px] font-semibold">Univers suivi — CAC 40 &amp; big caps</div>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                {positions.length} valeurs · mis à jour à 08:30 après la collecte nocturne
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

          <table className="w-full border-collapse">
            <thead>
              <tr>
                {["Valeur", "Panier", "Tendance", "Pattern", "Confiance", "Décision"].map((h) => (
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
              {filtered.map((p) => (
                <tr
                  key={p.t}
                  onClick={() => setSelected(p.t)}
                  className="cursor-pointer border-b"
                  style={{
                    borderColor: "var(--hairline)",
                    background: selected === p.t ? "var(--panel-alt)" : "transparent",
                  }}
                >
                  <td className="px-2.5 py-2.5">
                    <div className="mono font-semibold text-[13px]">{p.t}</div>
                    <div className="text-[13px]" style={{ color: "var(--text-dim)" }}>{p.n}</div>
                  </td>
                  <td className="px-2.5 py-2.5 text-[13px]" style={{ color: "var(--text-dim)" }}>{p.basket}</td>
                  <td className="px-2.5 py-2.5">
                    <Sparkline points={p.trend} color={decisionColor(p.dec)} />
                  </td>
                  <td className="px-2.5 py-2.5 text-[13px]">{p.pattern}</td>
                  <td className="px-2.5 py-2.5">
                    <div className="flex items-center">
                      <div className="w-[70px] h-[5px] rounded-full overflow-hidden" style={{ background: "var(--panel-alt)" }}>
                        <div className="h-full rounded-full" style={{ width: `${p.conf}%`, background: decisionColor(p.dec) }} />
                      </div>
                      <span className="mono text-xs ml-2">{p.conf}%</span>
                    </div>
                  </td>
                  <td className="px-2.5 py-2.5">
                    <span className="text-[11px] font-semibold px-2.5 py-1 rounded-md" style={tagStyle(p.dec)}>
                      {p.dec}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="grid gap-3 mt-4" style={{ gridTemplateColumns: "150px 150px 1fr" }}>
            {georgeIndex.slice(0, 2).map((g) => (
              <div key={g.basket} className="border rounded-[10px] p-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
                <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>George Index</div>
                <div className="flex items-center gap-2.5">
                  <Gauge value={g.score} color={scoreColor(g.score)} />
                  <div className="text-[11px] leading-tight" style={{ color: "var(--text-dim)" }}>
                    <b className="block text-[12.5px]" style={{ color: "var(--text)" }}>{g.basket}</b>
                  </div>
                </div>
              </div>
            ))}
            <div className="border rounded-[10px] p-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>Repères macro</div>
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
          <div className="px-5 pt-5">
            <h2 className="display text-[19px] font-semibold mb-0.5">{current.n}</h2>
            <div className="text-[12.5px] mb-4" style={{ color: "var(--text-dim)" }}>{current.t} · {current.basket}</div>
            <div className="border rounded-[10px] mb-4 overflow-hidden" style={{ borderColor: "var(--hairline)", background: "var(--panel-alt)" }}>
              <CandlestickChart trend={current.trend} seedKey={current.t} pattern={current.pattern} tpPct={current.tp} slPct={current.sl} />
            </div>
            <div className="flex items-center gap-1.5 -mt-2.5 mb-3 text-[11px]" style={{ color: "var(--text-dim)" }}>
              <span className="inline-block w-3.5" style={{ borderTop: "1.5px dashed var(--accent)" }} />
              Figure détectée par George : {current.pattern}
            </div>

            <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>Raisonnement de George</div>
            <div className="text-[13px] leading-relaxed" style={{ color: "var(--text-dim)" }}>{current.explain}</div>

            <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>Paramètres</div>
            {[
              ["Pattern détecté", current.pattern],
              ["Confiance", `${current.conf}%`],
              ["Décision", current.dec],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-[13px] py-1.5 border-b" style={{ borderColor: "var(--hairline)" }}>
                <span style={{ color: "var(--text-dim)" }}>{k}</span>
                <span className="mono" style={{ color: k === "Décision" ? decisionColor(current.dec) : "var(--text)" }}>{v}</span>
              </div>
            ))}

            <div className="text-[11px] uppercase tracking-wider mt-4 mb-2" style={{ color: "var(--text-dim)" }}>Niveaux proposés</div>
            <div className="flex gap-2.5 mt-2.5">
              <div className="flex-1 border rounded-lg p-2.5 text-center" style={{ borderColor: "var(--hairline)" }}>
                <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>Take-profit</div>
                <div className="mono font-semibold text-[15px] mt-1" style={{ color: "var(--positive)" }}>+{current.tp}%</div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>{(current.price * (1 + current.tp / 100)).toFixed(2)} €</div>
              </div>
              <div className="flex-1 border rounded-lg p-2.5 text-center" style={{ borderColor: "var(--hairline)" }}>
                <div className="text-[11px]" style={{ color: "var(--text-dim)" }}>Stop-loss</div>
                <div className="mono font-semibold text-[15px] mt-1" style={{ color: "var(--negative)" }}>{current.sl}%</div>
                <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>{(current.price * (1 + current.sl / 100)).toFixed(2)} €</div>
              </div>
            </div>
            <div className="flex gap-2 mt-3.5">
              <button
                className="flex-1 py-2.5 rounded-lg font-semibold text-[13px]"
                style={{ background: "var(--accent)", color: "#fff" }}
                onClick={() => setDockMsg(`Niveaux validés pour ${current.t} — TP +${current.tp}% / SL ${current.sl}%.`)}
              >
                Valider les niveaux
              </button>
              <button
                className="flex-1 py-2.5 rounded-lg font-semibold text-[13px] border"
                style={{ borderColor: "var(--hairline)" }}
                onClick={() => setDockMsg(`Ajustement des niveaux pour ${current.t} en cours de discussion.`)}
              >
                Ajuster
              </button>
            </div>
          </div>

          <div className="px-5 pb-5 mt-1.5">
            <div className="text-[11px] uppercase tracking-wider mb-2">Sous-agents — activité récente</div>
            {agentEvents.map((e) => (
              <div
                key={e.name + e.time}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md mb-1.5 text-[11.5px]"
                style={{
                  background: "var(--panel-alt)",
                  borderLeft: `3px solid ${
                    e.status === "validated" ? "var(--positive)" : e.status === "pending" ? "var(--warning)" : "var(--negative)"
                  }`,
                }}
              >
                <span className="mono font-semibold w-[92px] flex-shrink-0">{e.name}</span>
                <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap" style={{ color: "var(--text-dim)" }}>{e.desc}</span>
                <span className="mono text-[10.5px] flex-shrink-0" style={{ color: "var(--text-dim)" }}>{e.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Dock */}
      <div className="border-t px-5 py-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
        <div className="flex items-center gap-2.5">
          <div className="display font-semibold text-[13px] whitespace-nowrap" style={{ color: "var(--accent)" }}>George explique ›</div>
          <div className="text-[13px] flex-1" style={{ color: "var(--text-dim)" }}>
            {dockMsg ?? <>Sélectionnez une valeur pour voir le raisonnement complet, ou posez une question.</>}
          </div>
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg px-3 py-2.5 text-[13px] border"
            style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text)" }}
            placeholder="Poser une question à George…  (ex : pourquoi Airbus est en Achat ?)"
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.currentTarget.value.trim()) {
                setDockMsg(`Vous : ${e.currentTarget.value} — George consulte la mémoire historique et les sous-agents pertinents…`);
                e.currentTarget.value = "";
              }
            }}
          />
          <button
            className="text-xs px-3 py-1.5 rounded-full border whitespace-nowrap"
            style={{ background: "var(--panel-alt)", borderColor: "var(--hairline)", color: "var(--text-dim)" }}
            onClick={() =>
              setDockMsg(
                "🎙 Écoute… — \"George, les événements au détroit d'Ormuz peuvent avoir des conséquences économiques et financières.\" Collecte d'urgence déclenchée sur le panier Énergie."
              )
            }
          >
            🎙 Commande vocale
          </button>
        </div>
      </div>
    </div>
  );
}
