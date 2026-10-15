import { useGeorgeIndex } from "../api/queries";
import { scoreColor } from "../data";

// Score George Index d'un panier en matrice de 50 cases (1 case = 2 points),
// remplie dans la couleur du score (vert ≥ 75, orange ≥ 65, rouge sinon,
// voir scoreColor).
const CELLS = 50;

export default function GeorgeIndexTile({ basketId, basketName }) {
  const { data, isLoading } = useGeorgeIndex(basketId);
  const score = data?.george_index ?? null;
  const rounded = score == null ? null : Math.round(score);
  const filled = rounded == null ? 0 : Math.round(rounded / 2);
  const color = rounded == null ? "var(--hairline)" : scoreColor(rounded);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline gap-2 text-[12px]">
        <span className="font-semibold">{basketName}</span>
        {rounded != null && (
          <span>
            <b className="mono text-[13px]" style={{ color }}>
              {rounded}
            </b>
            <span style={{ color: "var(--text-dim)" }}> / 100</span>
          </span>
        )}
      </div>
      <div aria-hidden="true" className="grid gap-[2px]" style={{ gridTemplateColumns: "repeat(25, minmax(0, 1fr))" }}>
        {Array.from({ length: CELLS }, (_, i) => (
          <div key={i} style={{ height: 8, borderRadius: 2, background: i < filled ? color : "var(--panel-alt)" }} />
        ))}
      </div>
      {isLoading && (
        <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          Calcul…
        </span>
      )}
      {!isLoading && score == null && (
        <span className="text-[11px]" style={{ color: "var(--text-dim)" }}>
          Aucune figure active
        </span>
      )}
    </div>
  );
}
