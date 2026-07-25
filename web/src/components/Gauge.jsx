export default function Gauge({ value, color, size = 56 }) {
  const inner = size - 18;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          background: `conic-gradient(${color} ${value}%, var(--panel-alt) 0)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: (size - inner) / 2,
          left: (size - inner) / 2,
          width: inner,
          height: inner,
          borderRadius: "50%",
          background: "var(--panel)",
        }}
      />
      <div
        className="mono"
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 600,
        }}
      >
        {value}
      </div>
    </div>
  );
}
