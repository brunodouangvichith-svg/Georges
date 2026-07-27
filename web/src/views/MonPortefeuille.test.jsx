import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MonPortefeuille from "./MonPortefeuille";

vi.mock("../api/queries", () => ({
  useDecisions: vi.fn(),
}));

import { useDecisions } from "../api/queries";

const DECISIONS = [
  { id: 1, symbol: "AAA.PA", decision_type: "Achat", entry_price: 100, take_profit: 110, stop_loss: 95, confidence: 55 },
  { id: 2, symbol: "BBB.PA", decision_type: "Alléger", entry_price: 50, take_profit: 45, stop_loss: 55, confidence: 85 },
];

describe("MonPortefeuille", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useDecisions.mockReturnValue({ data: { items: DECISIONS }, isError: false });
  });

  it("shows an empty-state message when nothing has been selected yet", () => {
    render(<MonPortefeuille />);
    expect(screen.getByText(/aucune action sélectionnée/i)).toBeInTheDocument();
  });

  it("shows only the decisions previously selected via usePortfolioSelection's storage key", () => {
    window.localStorage.setItem("george.portfolio.decisionIds", JSON.stringify([2]));
    render(<MonPortefeuille />);
    expect(screen.getByText("BBB.PA")).toBeInTheDocument();
    expect(screen.queryByText("AAA.PA")).not.toBeInTheDocument();
  });

  it("shows a connection error banner when the API is unreachable", () => {
    useDecisions.mockReturnValue({ data: undefined, isError: true });
    render(<MonPortefeuille />);
    expect(screen.getByText(/impossible de contacter l'api/i)).toBeInTheDocument();
  });
});
