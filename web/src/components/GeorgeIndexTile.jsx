import Gauge from "./Gauge";
import { useGeorgeIndex } from "../api/queries";
import { scoreColor } from "../data";

export default function GeorgeIndexTile({ basketId, basketName }) {
  const { data, isLoading } = useGeorgeIndex(basketId);
  const score = data?.george_index ?? null;

  return (
    <div className="border rounded-[10px] p-3 flex flex-col gap-2" style={{ borderColor: "var(--hairline)", background: "var(--panel)" }}>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        George Index
      </div>
      <div className="flex items-center gap-2.5">
        <Gauge value={isLoading || score == null ? 0 : Math.round(score)} color={score != null ? scoreColor(score) : "var(--hairline)"} />
        <div className="text-[11px] leading-tight" style={{ color: "var(--text-dim)" }}>
          <b className="block text-[12.5px]" style={{ color: "var(--text)" }}>
            {basketName}
          </b>
          {!isLoading && score == null && <span>Aucune figure active</span>}
        </div>
      </div>
    </div>
  );
}
