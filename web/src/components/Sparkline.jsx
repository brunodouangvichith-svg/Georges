export default function Sparkline({ points, color, width = 90, height = 28 }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const norm = (p) => height - ((p - min) / (max - min || 1)) * height;
  const step = width / (points.length - 1);
  const d = points.map((p, i) => `${i * step},${norm(p)}`).join(" ");
  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <polyline points={d} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
