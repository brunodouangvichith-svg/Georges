import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MonPortefeuille from "./MonPortefeuille";

vi.mock("../api/queries", () => ({
  usePortfolios: vi.fn(),
  useDeletePortfolio: vi.fn(),
  useRemoveDecisionFromPortfolio: vi.fn(),
}));

import { useDeletePortfolio, usePortfolios, useRemoveDecisionFromPortfolio } from "../api/queries";

function mockEmptyApi() {
  usePortfolios.mockReturnValue({ data: [], isError: false });
  useDeletePortfolio.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useRemoveDecisionFromPortfolio.mockReturnValue({ mutate: vi.fn(), isPending: false });
}

const PORTFOLIO = {
  id: 1,
  name: "Mes achats",
  created_at: "2026-07-27T10:00:00Z",
  decisions: [
    { id: 2, symbol: "BBB.PA", decision_type: "Achat", entry_price: 50, take_profit: 55, stop_loss: 45, confidence: 85 },
  ],
};

describe("MonPortefeuille", () => {
  it("shows an empty-state message when no portfolio has been created yet", () => {
    mockEmptyApi();
    render(<MonPortefeuille />);
    expect(screen.getByText(/aucun portefeuille/i)).toBeInTheDocument();
  });

  it("shows a connection error banner when the API is unreachable", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: undefined, isError: true });
    render(<MonPortefeuille />);
    expect(screen.getByText(/impossible de contacter l'api/i)).toBeInTheDocument();
  });

  it("lists each saved portfolio's name and decisions", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText("Mes achats")).toBeInTheDocument();
    expect(screen.getByText("BBB.PA")).toBeInTheDocument();
  });

  it("removes a single decision from a portfolio via the API", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    const mutate = vi.fn();
    useRemoveDecisionFromPortfolio.mockReturnValue({ mutate, isPending: false });
    render(<MonPortefeuille />);

    fireEvent.click(screen.getByText("Retirer"));
    expect(mutate).toHaveBeenCalledWith({ portfolioId: 1, decisionId: 2 });
  });

  it("deletes an entire portfolio via the API", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    const mutate = vi.fn();
    useDeletePortfolio.mockReturnValue({ mutate, isPending: false });
    render(<MonPortefeuille />);

    fireEvent.click(screen.getByText("Supprimer le portefeuille"));
    expect(mutate).toHaveBeenCalledWith(1);
  });
});
