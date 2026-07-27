import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Paniers from "./Paniers";

vi.mock("../api/queries", () => ({
  useBaskets: vi.fn(),
  useSecurities: vi.fn(),
  useDecisions: vi.fn(),
  useGeorgeIndex: vi.fn(),
  useExplainDecision: vi.fn(),
}));

import { useBaskets, useDecisions, useExplainDecision, useGeorgeIndex, useSecurities } from "../api/queries";

function mockEmptyApi() {
  useBaskets.mockReturnValue({ data: [], isLoading: false, isError: false });
  useSecurities.mockReturnValue({ data: { items: [] }, isError: false });
  useDecisions.mockReturnValue({ data: { items: [] }, isError: false });
  useGeorgeIndex.mockReturnValue({ data: null, isLoading: false });
  useExplainDecision.mockReturnValue({ mutate: vi.fn(), isPending: false });
}

describe("Paniers", () => {
  it("shows empty-state messages when the database has no data yet", () => {
    mockEmptyApi();
    render(<Paniers />);
    expect(screen.getByText(/aucun panier/i)).toBeInTheDocument();
    expect(screen.getByText(/aucune décision enregistrée/i)).toBeInTheDocument();
    expect(screen.queryByText(/impossible de contacter l'api/i)).not.toBeInTheDocument();
  });

  it("shows a connection error banner instead of empty-states when the API is unreachable", () => {
    mockEmptyApi();
    useBaskets.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    render(<Paniers />);
    expect(screen.getByText(/impossible de contacter l'api/i)).toBeInTheDocument();
  });

  it("shows the basket's performance over 1j/1s/1m alongside its George Index", () => {
    mockEmptyApi();
    useBaskets.mockReturnValue({ data: [{ id: 1, name: "Tech FR", type: "secteur" }], isLoading: false, isError: false });
    useGeorgeIndex.mockReturnValue({
      data: { basket_id: 1, basket_name: "Tech FR", george_index: 70, performance_1j: 0.5, performance_1s: -2.3, performance_1m: 8.1 },
      isLoading: false,
    });
    render(<Paniers />);
    expect(screen.getByText("+0.5%")).toBeInTheDocument();
    expect(screen.getByText("-2.3%")).toBeInTheDocument();
    expect(screen.getByText("+8.1%")).toBeInTheDocument();
  });

  function mockDecisions() {
    useDecisions.mockReturnValue({
      data: {
        items: [
          { id: 1, symbol: "AAA.PA", decision_type: "Achat", status: "proposee", entry_price: 100, take_profit: 110, stop_loss: 95, confidence: 55, created_at: "2026-07-20T10:00:00Z" },
          { id: 2, symbol: "BBB.PA", decision_type: "Achat", status: "confirmee", entry_price: 50, take_profit: 55, stop_loss: 45, confidence: 85, created_at: "2026-07-25T10:00:00Z" },
          { id: 3, symbol: "CCC.PA", decision_type: "Alléger", status: "proposee", entry_price: 30, take_profit: 25, stop_loss: 35, confidence: 65, created_at: "2026-07-22T10:00:00Z" },
        ],
      },
      isError: false,
    });
  }

  it("filters the decisions table by a minimum-confidence preset", () => {
    mockEmptyApi();
    mockDecisions();
    render(<Paniers />);
    expect(screen.getByText("AAA.PA")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "≥ 60%" }));
    expect(screen.queryByText("AAA.PA")).not.toBeInTheDocument(); // confiance 55 < 60
    expect(screen.getByText("BBB.PA")).toBeInTheDocument();
    expect(screen.getByText("CCC.PA")).toBeInTheDocument();
  });

  it("combines the decision-type filter with a custom confidence threshold", () => {
    mockEmptyApi();
    mockDecisions();
    render(<Paniers />);

    // "je voudrais la décision d'achat pour une confiance supérieure à 70%"
    fireEvent.click(screen.getByRole("button", { name: "Achat" }));
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "70" } });

    expect(screen.getByText("BBB.PA")).toBeInTheDocument(); // Achat, 85%
    expect(screen.queryByText("AAA.PA")).not.toBeInTheDocument(); // Achat mais 55% < 70%
    expect(screen.queryByText("CCC.PA")).not.toBeInTheDocument(); // 65% >= ... mais Alléger, pas Achat
  });

  it("filters the decisions table by lifecycle status", () => {
    mockEmptyApi();
    mockDecisions();
    render(<Paniers />);
    expect(screen.getByText("AAA.PA")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Confirmée" }));
    expect(screen.getByText("BBB.PA")).toBeInTheDocument(); // confirmee
    expect(screen.queryByText("AAA.PA")).not.toBeInTheDocument(); // proposee
    expect(screen.queryByText("CCC.PA")).not.toBeInTheDocument(); // proposee
  });

  it("sorts the decisions table by clicking a column header", () => {
    mockEmptyApi();
    mockDecisions();
    render(<Paniers />);

    const rowsInOrder = () => screen.getAllByRole("row").slice(1).map((r) => r.cells[0].textContent);
    expect(rowsInOrder()).toEqual(["BBB.PA", "CCC.PA", "AAA.PA"]); // tri initial : créée le, plus récent d'abord

    fireEvent.click(screen.getByRole("button", { name: /Confiance/ }));
    expect(rowsInOrder()).toEqual(["BBB.PA", "CCC.PA", "AAA.PA"]); // confiance déjà décroissante dans ce jeu

    fireEvent.click(screen.getByRole("button", { name: /Confiance/ })); // re-clic -> inverse
    expect(rowsInOrder()).toEqual(["AAA.PA", "CCC.PA", "BBB.PA"]);
  });

  it("opens a popup with a prompt to ask George for the full explanation when a decision row is clicked", () => {
    mockEmptyApi();
    mockDecisions();
    const mutate = vi.fn();
    useExplainDecision.mockReturnValue({ mutate, isPending: false });
    render(<Paniers />);

    fireEvent.click(screen.getByText("AAA.PA").closest("tr"));
    expect(screen.getByText("Demander l'explication complète à George")).toBeInTheDocument();
    expect(screen.getByText(/Confiance 55%/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("Demander l'explication complète à George"));
    expect(mutate).toHaveBeenCalledWith({ decisionId: 1 }, expect.anything());
  });
});
