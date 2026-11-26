import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockContainerWidth } from "../test/containerWidth";
import BondHistoryChart from "./BondHistoryChart";

const day = (ago) => new Date(Date.now() - ago * 864e5).toISOString().slice(0, 10);
const series = [
  { key: "OAT", short: "OAT 10a", color: "var(--accent)", points: [{ observed_at: day(200), value_pct: 3.1 }, { observed_at: day(5), value_pct: 3.4 }] },
  { key: "UST", short: "UST 2a", color: "var(--text-dim)", dash: "5 3", points: [{ observed_at: day(200), value_pct: 4 }, { observed_at: day(5), value_pct: 3.9 }] },
];

describe("BondHistoryChart", () => {
  afterEach(() => vi.restoreAllMocks());

  it("labels the end of each curve inside the chart on a wide frame", () => {
    render(<BondHistoryChart series={series} rangeDays={365} />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("viewBox")).toBe("0 0 760 340");
    expect(chart.textContent).toContain("OAT 10a 3.40 %");
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("moves the last values to a legend below the chart on a narrow frame", () => {
    mockContainerWidth(290);
    render(<BondHistoryChart series={series} rangeDays={365} />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("viewBox")).toBe("0 0 290 240");
    expect(chart.textContent).not.toContain("OAT 10a");
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["OAT 10a 3.40 %", "UST 2a 3.90 %"]);
  });

  it("says when there is no history", () => {
    render(<BondHistoryChart series={[]} rangeDays={365} />);
    expect(screen.getByText(/pas encore d'historique/i)).toBeInTheDocument();
  });
});
