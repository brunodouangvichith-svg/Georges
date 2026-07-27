import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import WatchlistRow from "./WatchlistRow";

vi.mock("../api/queries", () => ({
  useSecurityPatterns: vi.fn(),
  useSecurityPrices: vi.fn(),
}));

import { useSecurityPatterns, useSecurityPrices } from "../api/queries";

const security = { symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique / Défense" };

function renderRow(props = {}) {
  return render(
    <table>
      <tbody>
        <WatchlistRow security={security} decision={undefined} selected={false} onSelect={() => {}} {...props} />
      </tbody>
    </table>
  );
}

describe("WatchlistRow", () => {
  it("shows placeholders when there is no pattern, price history, or decision", () => {
    useSecurityPatterns.mockReturnValue({ data: { items: [] } });
    useSecurityPrices.mockReturnValue({ data: { items: [] } });
    renderRow();
    expect(screen.getByText("AIR.PA")).toBeInTheDocument();
    expect(screen.getByText("Aéronautique / Défense")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3); // tendance, pattern/confiance, décision
  });

  it("shows the pattern, confidence, and decision tag when available", () => {
    useSecurityPatterns.mockReturnValue({ data: { items: [{ pattern_type: "Bull Flag", confidence: 82.4 }] } });
    useSecurityPrices.mockReturnValue({ data: { items: [{ close: 100 }, { close: 102 }, { close: 105 }] } });
    renderRow({ decision: { decision_type: "Achat" } });
    expect(screen.getByText("Bull Flag")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByText("Achat")).toBeInTheDocument();
  });

  it("calls onSelect with the symbol when clicked", () => {
    useSecurityPatterns.mockReturnValue({ data: { items: [] } });
    useSecurityPrices.mockReturnValue({ data: { items: [] } });
    const onSelect = vi.fn();
    renderRow({ onSelect });
    fireEvent.click(screen.getByText("AIR.PA"));
    expect(onSelect).toHaveBeenCalledWith("AIR.PA");
  });
});
