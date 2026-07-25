import { useMemo } from "react";
import { generateOHLC } from "../lib/ohlc";

// Superposition du pattern détecté, tracée à partir des extrema réels de la série générée.
function argext(candles, [from, to], key, mode) {
  let best = from;
  for (let i = from; i <= to; i++) {
    if (mode === "max" ? candles[i][key] > candles[best][key] : candles[i][key] < candles[best][key]) best = i;
  }
  return best;
}

export default function CandlestickChart({ trend, seedKey, pattern, tpPct, slPct, width = 290, height = 150 }) {
  const candles = useMemo(() => generateOHLC(trend, seedKey), [trend, seedKey]);

  const lastClose = candles[candles.length - 1].close;
  const tpLevel = lastClose * (1 + tpPct / 100);
  const slLevel = lastClose * (1 + slPct / 100);
  const allVals = candles.flatMap((c) => [c.high, c.low]).concat([tpLevel, slLevel]);
  const max = Math.max(...allVals);
  const min = Math.min(...allVals);
  const pad = 14;
  const plotW = width - 50;
  const scaleY = (v) => pad + (height - 2 * pad) * (1 - (v - min) / ((max - min) || 1));
  const step = plotW / candles.length;
  const bodyW = Math.max(2, step * 0.55);
  const x = (i) => i * step + step / 2;

  const n = candles.length;
  const third = Math.max(1, Math.floor(n / 3));
  const firstIdx = [0, third - 1];
  const lastIdx = [n - third, n - 1];
  const OVERLAY = "var(--accent)";

  const isChannel = /triangle|wedge|flag/i.test(pattern);
  let overlay;
  if (isChannel) {
    const upA = argext(candles, firstIdx, "high", "max");
    const upB = argext(candles, lastIdx, "high", "max");
    const loA = argext(candles, firstIdx, "low", "min");
    const loB = argext(candles, lastIdx, "low", "min");
    overlay = (
      <>
        <line x1={x(upA)} y1={scaleY(candles[upA].high)} x2={x(upB)} y2={scaleY(candles[upB].high)} stroke={OVERLAY} strokeWidth={1.5} strokeDasharray="5,4" />
        <line x1={x(loA)} y1={scaleY(candles[loA].low)} x2={x(loB)} y2={scaleY(candles[loB].low)} stroke={OVERLAY} strokeWidth={1.5} strokeDasharray="5,4" />
        <circle cx={x(upA)} cy={scaleY(candles[upA].high)} r={2.5} fill={OVERLAY} />
        <circle cx={x(upB)} cy={scaleY(candles[upB].high)} r={2.5} fill={OVERLAY} />
        <circle cx={x(loA)} cy={scaleY(candles[loA].low)} r={2.5} fill={OVERLAY} />
        <circle cx={x(loB)} cy={scaleY(candles[loB].low)} r={2.5} fill={OVERLAY} />
      </>
    );
  } else {
    const bearish = /top|breakdown|shoulders(?!.*inverse)/i.test(pattern) && !/inverse/i.test(pattern);
    let touch1, touch2, level;
    if (bearish) {
      touch1 = argext(candles, [0, Math.floor(n / 2)], "high", "max");
      touch2 = argext(candles, [Math.floor(n / 2), n - 1], "high", "max");
      level = (candles[touch1].high + candles[touch2].high) / 2;
    } else {
      touch1 = argext(candles, [0, Math.floor(n / 2)], "low", "min");
      touch2 = argext(candles, [Math.floor(n / 2), n - 1], "low", "min");
      level = (candles[touch1].low + candles[touch2].low) / 2;
    }
    const y = scaleY(level);
    overlay = (
      <>
        <line x1={0} y1={y} x2={plotW} y2={y} stroke={OVERLAY} strokeWidth={1.5} strokeDasharray="5,4" />
        <circle cx={x(touch1)} cy={y} r={2.5} fill={OVERLAY} />
        <circle cx={x(touch2)} cy={y} r={2.5} fill={OVERLAY} />
      </>
    );
  }

  const priceTag = (level, fill, textFill) => (
    <>
      <line x1={0} y1={scaleY(level)} x2={width - 46} y2={scaleY(level)} stroke={fill} strokeWidth={1.3} strokeDasharray="4,3" />
      <rect x={width - 45} y={scaleY(level) - 8} width={45} height={16} rx={3} fill={fill} />
      <text x={width - 22.5} y={scaleY(level) + 4} textAnchor="middle" fontSize={9.5} fontFamily="IBM Plex Mono" fill={textFill} fontWeight={600}>
        {level.toFixed(2)}
      </text>
    </>
  );

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {priceTag(tpLevel, "var(--positive)", "#08130d")}
      {priceTag(slLevel, "var(--negative)", "#1a0a0a")}

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
      {overlay}

      <line x1={0} y1={scaleY(lastClose)} x2={width - 46} y2={scaleY(lastClose)} stroke="var(--text-dim)" strokeWidth={1} strokeDasharray="2,3" />
      <rect x={width - 45} y={scaleY(lastClose) - 8} width={45} height={16} rx={3} fill="var(--panel-alt)" stroke="var(--hairline)" />
      <text x={width - 22.5} y={scaleY(lastClose) + 4} textAnchor="middle" fontSize={9.5} fontFamily="IBM Plex Mono" fill="var(--text)" fontWeight={600}>
        {lastClose.toFixed(2)}
      </text>
    </svg>
  );
}
