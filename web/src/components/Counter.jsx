// Compteur d'en-tête partagé par les écrans Univers, Paniers et Mon
// Portefeuille : libellé, valeur, et barre fine proportionnelle à `ratio`
// (0-1) dans la couleur qui porte le sens (vert/orange/rouge/bleu).
// `value` peut être un nœud React (ex. un montant coloré).
export default function Counter({ label, value, ratio = 0, color = "var(--accent)", valueColor }) {
  return (
    <div className="flex flex-col gap-1.5" style={{ minWidth: 110, flex: "1 1 110px", maxWidth: 190 }}>
      <div className="gd-label" style={{ color: "var(--text-dim)" }}>
        {label}
      </div>
      <div className="mono text-[18px] font-bold" style={{ color: valueColor ?? "var(--text)" }}>
        {value}
      </div>
      <div style={{ height: 3, background: "var(--hairline)", position: "relative" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: `${Math.round(Math.max(0, Math.min(1, ratio)) * 100)}%`,
            background: color,
            borderRadius: 2,
          }}
        />
      </div>
    </div>
  );
}
