import Sparkline from "./Sparkline";
import { useSecurityPatterns, useSecurityPrices } from "../api/queries";
import { decisionColor } from "../data";

function tagStyle(dec) {
  const color = decisionColor(dec);
  return { color, background: `color-mix(in srgb, ${color} 15%, transparent)` };
}

// Une ligne = ses propres requêtes (pattern le plus récent + un court
// historique pour le sparkline) — pas d'endpoint de lot côté API pour ça,
// voir la note dans src/api/queries.js.
export default function WatchlistRow({ security, decision, selected, onSelect }) {
  const { data: patternsPage } = useSecurityPatterns(security.symbol, { limit: 1 });
  const { data: pricesPage } = useSecurityPrices(security.symbol, { limit: 20 });

  const pattern = patternsPage?.items?.[0] ?? null;
  const closes = (pricesPage?.items ?? []).map((bar) => bar.close);
  const decisionType = decision?.decision_type ?? null;
  const sparkColor = decisionType ? decisionColor(decisionType) : "var(--text-dim)";

  return (
    <tr
      onClick={() => onSelect(security.symbol)}
      className="cursor-pointer border-b"
      style={{ borderColor: "var(--hairline)", background: selected ? "var(--panel-alt)" : "transparent" }}
    >
      <td className="px-2.5 py-2.5">
        <div className="mono font-semibold text-[13px]">{security.symbol}</div>
        <div className="text-[13px]" style={{ color: "var(--text-dim)" }}>
          {security.name}
        </div>
      </td>
      <td className="px-2.5 py-2.5 text-[13px]" style={{ color: "var(--text-dim)" }}>
        {security.sector}
      </td>
      <td className="px-2.5 py-2.5">
        {closes.length > 1 ? (
          <Sparkline points={closes} color={sparkColor} />
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
      <td className="px-2.5 py-2.5 text-[13px]">{pattern?.pattern_type ?? "—"}</td>
      <td className="px-2.5 py-2.5">
        {pattern ? (
          <div className="flex items-center">
            <div className="w-[70px] h-[5px] rounded-full overflow-hidden" style={{ background: "var(--panel-alt)" }}>
              <div className="h-full rounded-full" style={{ width: `${pattern.confidence}%`, background: sparkColor }} />
            </div>
            <span className="mono text-xs ml-2">{Math.round(pattern.confidence)}%</span>
          </div>
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
      <td className="px-2.5 py-2.5">
        {decisionType ? (
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-md" style={tagStyle(decisionType)}>
            {decisionType}
          </span>
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
    </tr>
  );
}
