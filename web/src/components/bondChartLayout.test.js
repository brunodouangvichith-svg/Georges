import { describe, expect, it } from "vitest";
import { buildChart } from "./bondChartLayout";

const now = Date.parse("2026-10-15T00:00:00Z");

describe("buildChart", () => {
  it("returns null when no series has points in the range", () => {
    expect(buildChart([{ key: "A", points: [{ observed_at: "2020-01-01", value_pct: 3 }] }], 365, now)).toBeNull();
  });

  it("keeps only points inside the range and labels the last value", () => {
    const chart = buildChart(
      [{ key: "A", points: [{ observed_at: "2020-01-01", value_pct: 1 }, { observed_at: "2026-05-01", value_pct: 3.2 }, { observed_at: "2026-09-01", value_pct: 3.4 }] }],
      365,
      now
    );
    expect(chart.lines[0].points).toHaveLength(2);
    expect(chart.lines[0].lastValue).toBe(3.4);
  });

  it("never lets two end labels overlap", () => {
    const pts = (v) => [{ observed_at: "2026-06-01", value_pct: v }, { observed_at: "2026-09-01", value_pct: v }];
    const chart = buildChart([{ key: "A", points: pts(3.40) }, { key: "B", points: pts(3.41) }, { key: "C", points: pts(5) }], 365, now);
    const ys = Object.values(chart.labelY).sort((a, b) => a - b);
    for (let i = 1; i < ys.length; i++) expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(14);
  });
});
