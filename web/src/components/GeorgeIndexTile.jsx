import { useGeorgeIndex } from "../api/queries";

// Thème Paper Lab : le score s'affiche en matrice de 50 cases (1 case = 2
// points) plutôt qu'en jauge colorée — la lecture passe par le remplissage,
// pas par la couleur.
const CELLS = 50;

export default function GeorgeIndexTile({ basketId, basketName }) {
  const { data, isLoading } = useGeorgeIndex(basketId);
  const score = data?.george_index ?? null;
  const rounded = score == null ? null : Math.round(score);
  const filled = rounded == null ? 0 : Math.round(rounded / 2);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline gap-2 text-[11.5px]">
        <span className="font-semibold">{basketName}</span>
        {rounded != null && (
          <span>
            <b className="text-[13px]">{rounded}</b>
            <span style={{ color: "var(--text-dim)" }}> / 100</span>
          </span>
        )}
      </div>
      <div aria-hidden="true" className="grid gap-[2px]" style={{ gridTemplateColumns: "repeat(25, minmax(0, 1fr))" }}>
        {Array.from({ length: CELLS }, (_, i) => (
          <div key={i} style={{ height: 8, background: i < filled ? "var(--text)" : "var(--accent-dim)" }} />
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
