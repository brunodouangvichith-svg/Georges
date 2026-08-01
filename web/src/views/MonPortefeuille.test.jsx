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
  created_at: "2026-07-20T10:00:00Z",
  decisions: [
    {
      id: 2,
      symbol: "BBB.PA",
      decision_type: "Achat",
      entry_price: 50,
      current_price: 55,
      take_profit: 60,
      stop_loss: 45,
      pnl_pct: 10,
      quantity: 12,
      created_at: "2026-07-20T14:32:00Z",
      price_updated_at: "2026-07-27T12:00:00Z",
    },
  ],
  total_pnl_amount: 60,
  total_invested: 600,
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

  it("shows Prix and PnL columns instead of Confiance, with the current price and per-decision PnL", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText("Prix")).toBeInTheDocument();
    expect(screen.getByText("PnL")).toBeInTheDocument();
    expect(screen.queryByText("Confiance")).not.toBeInTheDocument();
    expect(screen.getByText("55.00 €")).toBeInTheDocument(); // current_price
    expect(screen.getByText("+10.0%")).toBeInTheDocument(); // pnl_pct
  });

  it("shows Date and Heure columns with the price's last-update time, not the decision's creation time", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Heure")).toBeInTheDocument();
    // price_updated_at (27/07/2026) doit s'afficher, pas created_at (20/07/2026).
    expect(screen.getByText("27/07/2026")).toBeInTheDocument();
    expect(screen.queryByText("20/07/2026")).not.toBeInTheDocument();
    expect(screen.getByText(/^\d{2}:\d{2}$/)).toBeInTheDocument();
  });

  it("shows a dash for Date/Heure when no price is available for a decision", () => {
    mockEmptyApi();
    const portfolioWithoutPrice = {
      ...PORTFOLIO,
      decisions: [{ ...PORTFOLIO.decisions[0], price_updated_at: null, current_price: null, pnl_pct: null }],
    };
    usePortfolios.mockReturnValue({ data: [portfolioWithoutPrice], isError: false });
    render(<MonPortefeuille />);
    expect(screen.queryByText("27/07/2026")).not.toBeInTheDocument();
  });

  it("shows the portfolio's creation date next to the 'Demander à George' button", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText(/créé le 20\/07\/2026/i)).toBeInTheDocument();
  });

  it("shows the portfolio-level PnL total when quantities and prices are available", () => {
    mockEmptyApi();
    usePortfolios.mockReturnValue({ data: [PORTFOLIO], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText("PnL du portefeuille")).toBeInTheDocument();
    expect(screen.getByText("+60.00 € (+10.0%)")).toBeInTheDocument();
  });

  it("shows a fallback message instead of a PnL total when no decision has a quantity yet", () => {
    mockEmptyApi();
    const portfolioWithoutPnl = {
      ...PORTFOLIO,
      decisions: [{ ...PORTFOLIO.decisions[0], quantity: null, current_price: null, pnl_pct: null }],
      total_pnl_amount: null,
      total_invested: null,
    };
    usePortfolios.mockReturnValue({ data: [portfolioWithoutPnl], isError: false });
    render(<MonPortefeuille />);
    expect(screen.getByText(/renseignez des quantités/i)).toBeInTheDocument();
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

    fireEvent.click(screen.getByText("🎙 Demander à George pour répartir le budget du portefeuille"));
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

    fireEvent.click(screen.getByText("🎙 Demander à George pour répartir le budget du portefeuille")); // fixe le portefeuille actif (ref)
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

    fireEvent.click(screen.getByText("🎙 Demander à George pour répartir le budget du portefeuille"));
    act(() => capturedConfig.onFinal("Georges, que penses-tu de ce portefeuille ?"));

    expect(allocateMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/je n'ai pas compris de montant/i)).toBeInTheDocument();
  });
});
