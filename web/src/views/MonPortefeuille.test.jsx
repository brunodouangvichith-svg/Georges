import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MonPortefeuille from "./MonPortefeuille";

vi.mock("../api/queries", () => ({
  usePortfolios: vi.fn(),
  useDeletePortfolio: vi.fn(),
  useRemoveDecisionFromPortfolio: vi.fn(),
  useAllocateBudget: vi.fn(),
}));

vi.mock("../hooks/useVoiceCapture", () => ({
  useVoiceCapture: vi.fn(),
}));

import {
  useAllocateBudget,
  useDeletePortfolio,
  usePortfolios,
  useRemoveDecisionFromPortfolio,
} from "../api/queries";
import { useVoiceCapture } from "../hooks/useVoiceCapture";

function mockEmptyApi() {
  usePortfolios.mockReturnValue({ data: [], isError: false });
  useDeletePortfolio.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useRemoveDecisionFromPortfolio.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useAllocateBudget.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useVoiceCapture.mockReturnValue({ start: vi.fn(), stop: vi.fn(), abort: vi.fn() });
}

const PORTFOLIO = {
  id: 1,
  name: "Mes achats",
  created_at: "2026-07-27T10:00:00Z",
  decisions: [
    { id: 2, symbol: "BBB.PA", decision_type: "Achat", entry_price: 50, take_profit: 55, stop_loss: 45, confidence: 85, quantity: 12 },
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

  it("lists each saved portfolio's name, decisions and quantity, without a Décision column", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText("Mes achats")).toBeInTheDocument();
    expect(screen.getByText("BBB.PA")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument(); // quantité
    expect(screen.queryByText("Décision")).not.toBeInTheDocument();
    expect(screen.getByText("Quantité")).toBeInTheDocument();
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

  it("starts voice capture for the right portfolio when 'Demander à George' is clicked", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    const start = vi.fn();
    useVoiceCapture.mockReturnValue({ start, stop: vi.fn(), abort: vi.fn() });
    render(<MonPortefeuille />);

    fireEvent.click(screen.getByText("🎙 Demander à George"));
    expect(start).toHaveBeenCalled();
  });

  it("parses a spoken budget and calls the allocate endpoint for the active portfolio", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    const allocateMutate = vi.fn();
    useAllocateBudget.mockReturnValue({ mutate: allocateMutate, isPending: false });
    let capturedConfig;
    useVoiceCapture.mockImplementation((config) => {
      capturedConfig = config;
      return { start: vi.fn(), stop: vi.fn(), abort: vi.fn() };
    });
    render(<MonPortefeuille />);

    fireEvent.click(screen.getByText("🎙 Demander à George")); // fixe le portefeuille actif (ref)
    act(() => capturedConfig.onFinal("Georges, répartis un budget de 100 000 euros entre ces actions"));

    expect(allocateMutate).toHaveBeenCalledWith({ portfolioId: 1, budget: 100000 }, expect.anything());
  });

  it("shows an error instead of calling the API when no budget amount is understood", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    const allocateMutate = vi.fn();
    useAllocateBudget.mockReturnValue({ mutate: allocateMutate, isPending: false });
    let capturedConfig;
    useVoiceCapture.mockImplementation((config) => {
      capturedConfig = config;
      return { start: vi.fn(), stop: vi.fn(), abort: vi.fn() };
    });
    render(<MonPortefeuille />);

    fireEvent.click(screen.getByText("🎙 Demander à George"));
    act(() => capturedConfig.onFinal("Georges, que penses-tu de ce portefeuille ?"));

    expect(allocateMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/je n'ai pas compris de montant/i)).toBeInTheDocument();
  });
});
