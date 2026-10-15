import Sparkline from "./Sparkline";
import { useSecurityPatterns, useSecurityPrices } from "../api/queries";
import { decisionColor, decisionTagClass } from "../data";

const cell = { padding: "8px 10px", borderBottom: "1px solid var(--hairline)" };

// Une ligne = ses propres requêtes (pattern le plus récent + un court
// historique pour le sparkline) — pas d'endpoint de lot côté API pour ça,
// voir la note dans src/api/queries.js. Le radar de l'écran Univers
// réutilise la même clé de cache pour la figure (useLatestPatterns).
export default function WatchlistRow({ security, decision, selected, onSelect }) {
  const { data: patternsPage } = useSecurityPatterns(security.symbol, { limit: 1 });
  const { data: pricesPage } = useSecurityPrices(security.symbol, { limit: 20 });

  const pattern = patternsPage?.items?.[0] ?? null;
  const closes = (pricesPage?.items ?? []).map((bar) => bar.close);
  const decisionType = decision?.decision_type ?? null;
  const color = decisionType ? decisionColor(decisionType) : "var(--text-dim)";

  return (
    <tr
      onClick={() => onSelect(security.symbol)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(security.symbol);
        }
      }}
      tabIndex={0}
      aria-selected={selected}
      className="cursor-pointer gd-focus"
      style={{ background: selected ? "var(--panel-alt)" : "transparent" }}
    >
      <td style={cell}>
        <div className="mono font-semibold text-[13px]">{security.symbol}</div>
        <div className="text-[12.5px]" style={{ color: "var(--text-dim)" }}>
          {security.name}
        </div>
      </td>
      <td className="text-[12.5px]" style={{ ...cell, color: "var(--text-dim)" }}>
        {security.sector}
      </td>
      <td style={cell}>
        {closes.length > 1 ? (
          <Sparkline points={closes} color={color} width={80} height={22} />
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
      <td className="text-[12.5px]" style={cell}>
        {pattern?.pattern_type ?? "—"}
      </td>
      <td style={cell}>
        {pattern ? (
          <div className="flex items-center">
            <div className="w-[64px] h-[5px] rounded-full overflow-hidden" style={{ background: "var(--panel-alt)" }}>
              <div className="h-full rounded-full" style={{ width: `${pattern.confidence}%`, background: color }} />
            </div>
            <span className="mono text-xs ml-2">{Math.round(pattern.confidence)}%</span>
          </div>
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
      <td style={cell}>
        {decisionType ? (
          <span className={decisionTagClass(decisionType)}>{decisionType}</span>
        ) : (
          <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
            —
          </span>
        )}
      </td>
    </tr>
  );
}
