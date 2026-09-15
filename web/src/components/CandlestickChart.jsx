import { useMemo } from "react";

// Superposition dérivée du `context` réel de `patterns_detected` (voir
// engine/patterns/*.py), pas d'une heuristique locale sur les chandeliers —
// les points {index, price} sont marqués, les niveaux nommés
// resistance/support (bruts ou via un point) sont tracés en ligne
// horizontale. Même logique que `engine/notebooks/pattern_validation.ipynb`
// côté Python, portée ici pour l'UI. `left_rim`/`right_rim`/`handle_low`
// (Cup & Handle) jouent le même rôle conceptuel que resistance/support avec
// un nom différent — ajoutés ici pour que cette figure soit tracée en ligne
// elle aussi, pas seulement en marqueurs (bug réel trouvé en recevant un
// email de partage montrant un Cup & Handle sans aucune ligne).
const LEVEL_KEYS = new Set(["resistance", "support", "left_rim", "right_rim", "handle_low"]);

function buildOverlay(context, indexOffset, candleCount) {
  const markers = [];
  const hlines = [];
  if (!context) return { markers, hlines };

  for (const [key, value] of Object.entries(context)) {
    const isLevelKey = LEVEL_KEYS.has(key);
    if (value && typeof value === "object" && !Array.isArray(value) && "price" in value) {
      const price = value.price;
      if ("index" in value) {
        const relIdx = value.index - indexOffset;
        if (relIdx >= 0 && relIdx < candleCount) markers.push([relIdx, price]);
      }
      if ("points" in value) {
        for (const idx of value.points) {
          const relIdx = idx - indexOffset;
          if (relIdx >= 0 && relIdx < candleCount) markers.push([relIdx, price]);
        }
      }
      if ("points" in value || isLevelKey) hlines.push(price);
    } else if (isLevelKey && typeof value === "number") {
      hlines.push(value);
    }
  }
  return { markers, hlines };
}

export default function CandlestickChart({
  candles,
  loading = false,
  error = false,
  context = null,
  indexOffset = 0,
  takeProfit = null,
  stopLoss = null,
  width = 290,
  height = 150,
}) {
  const { markers, hlines } = useMemo(
    () => buildOverlay(context, indexOffset, candles?.length ?? 0),
    [context, indexOffset, candles?.length]
  );

  // `loading`/`error` distincts d'un historique réellement vide — trouvé en
  // debuggant en direct un cas où le graphique affichait "pas d'historique"
  // pour un titre qui en avait bien un (255 785 lignes vérifiées en base) :
  // le service Render (plan gratuit) venait de se réveiller après une
  // pause, la requête a pris ~84s, et pendant ce temps `candles` valait `[]`
  // par défaut (chargement) -- rendu identique à "vraiment aucune donnée",
  // ce qui donnait un message trompeur pendant que le serveur répondait
  // encore.
  const emptyStateMessage = loading
    ? "Chargement de l'historique…"
    : error
      ? "Le serveur met parfois jusqu'à 1-2 minutes à répondre après une pause (plan gratuit) — réessaie dans un instant."
      : "Pas d'historique de prix disponible pour ce titre.";

  if (loading || error || !candles || candles.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-dim)",
          fontSize: 12,
          textAlign: "center",
          padding: "0 12px",
        }}
      >
        {emptyStateMessage}
      </div>
    );
  }

  const lastClose = candles[candles.length - 1].close;
  const levels = [...hlines, lastClose];
  if (takeProfit != null) levels.push(takeProfit);
  if (stopLoss != null) levels.push(stopLoss);
  const allVals = candles.flatMap((c) => [c.high, c.low]).concat(levels);
  const max = Math.max(...allVals);
  const min = Math.min(...allVals);
  const pad = 14;
  const plotW = width - 50;
  const scaleY = (v) => pad + (height - 2 * pad) * (1 - (v - min) / (max - min || 1));
  const step = plotW / candles.length;
  const bodyW = Math.max(2, step * 0.55);
  const x = (i) => i * step + step / 2;

  const priceTag = (level, fill, textFill, key) => (
    <g key={key}>
      <line x1={0} y1={scaleY(level)} x2={width - 46} y2={scaleY(level)} stroke={fill} strokeWidth={1.3} strokeDasharray="4,3" />
      <rect x={width - 45} y={scaleY(level) - 8} width={45} height={16} rx={3} fill={fill} />
      <text x={width - 22.5} y={scaleY(level) + 4} textAnchor="middle" fontSize={9.5} fontFamily="IBM Plex Mono" fill={textFill} fontWeight={600}>
        {level.toFixed(2)}
      </text>
    </g>
  );

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {takeProfit != null && priceTag(takeProfit, "var(--positive)", "#08130d", "tp")}
      {stopLoss != null && priceTag(stopLoss, "var(--negative)", "#1a0a0a", "sl")}

      {candles.map((c, i) => {
        const up = c.close >= c.open;
        const color = up ? "var(--positive)" : "var(--negative)";
        const yOpen = scaleY(c.open);
        const yClose = scaleY(c.close);
        const yHigh = scaleY(c.high);
        const yLow = scaleY(c.low);
        const bodyTop = Math.min(yOpen, yClose);
        const bodyH = Math.max(1, Math.abs(yClose - yOpen));
        return (
          <g key={i}>
            <line x1={x(i)} y1={yHigh} x2={x(i)} y2={yLow} stroke={color} strokeWidth={1} />
            <rect x={x(i) - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH} fill={color} />
          </g>
        );
      })}

      {hlines.map((level, i) => (
        <line
          key={`hline-${i}`}
          x1={0}
          y1={scaleY(level)}
          x2={plotW}
          y2={scaleY(level)}
          stroke="var(--accent)"
          strokeWidth={1.5}
          strokeDasharray="5,4"
        />
      ))}
      {markers.map(([idx, price], i) => (
        <circle key={`marker-${i}`} cx={x(idx)} cy={scaleY(price)} r={2.5} fill="var(--accent)" />
      ))}

      <line x1={0} y1={scaleY(lastClose)} x2={width - 46} y2={scaleY(lastClose)} stroke="var(--text-dim)" strokeWidth={1} strokeDasharray="2,3" />
      <rect x={width - 45} y={scaleY(lastClose) - 8} width={45} height={16} rx={3} fill="var(--panel-alt)" stroke="var(--hairline)" />
      <text x={width - 22.5} y={scaleY(lastClose) + 4} textAnchor="middle" fontSize={9.5} fontFamily="IBM Plex Mono" fill="var(--text)" fontWeight={600}>
        {lastClose.toFixed(2)}
      </text>
    </svg>
  );
}
