// `hidden: true` sur les getByRole : contourne le même bug de jsdom 30 que
// Obligataire.test.jsx (getComputedStyle plante sur certains styles inline).
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Trading from "./Trading";

vi.mock("../api/queries", () => ({
  useDecisions: vi.fn(),
  useConfirmDecision: vi.fn(),
  useProposeLevels: vi.fn(),
  useConfirmExit: vi.fn(),
  useExplainDecision: vi.fn(),
  useProposeDecisions: vi.fn(),
  useMonitorDecisions: vi.fn(),
}));

import {
  useConfirmDecision,
  useConfirmExit,
  useDecisions,
  useExplainDecision,
  useMonitorDecisions,
  useProposeDecisions,
  useProposeLevels,
} from "../api/queries";

const base = { pattern_id: 3, confidence: 72.4, rationale: null, exit_scenario: null, exit_volume_confirmed: null, exit_justification: null, exit_proposed_at: null, created_at: "2026-10-10T08:00:00Z" };
const byStatus = {
  proposee: [{ ...base, id: 1, symbol: "AIR.PA", decision_type: "Achat", status: "proposee", entry_price: 170, take_profit: 182.4, stop_loss: 158.9 }],
  confirmee: [],
  sortie_proposee: [{ ...base, id: 2, symbol: "KER.PA", decision_type: "Alléger", status: "sortie_proposee", entry_price: 300, take_profit: 270, stop_loss: 315, exit_scenario: "sortie_totale", exit_volume_confirmed: true, exit_justification: "Stop-loss franchi avec volume." }],
  cloturee: [],
};
const mutation = () => ({ mutate: vi.fn(), isPending: false, variables: undefined });

describe("Trading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDecisions.mockImplementation(({ status }) => ({ data: { items: byStatus[status], total: byStatus[status].length }, isLoading: false, isError: false }));
    useConfirmDecision.mockReturnValue(mutation());
    useProposeLevels.mockReturnValue(mutation());
    useConfirmExit.mockReturnValue(mutation());
    useExplainDecision.mockReturnValue(mutation());
    useProposeDecisions.mockReturnValue(mutation());
    useMonitorDecisions.mockReturnValue(mutation());
  });

  it("shows one column per lifecycle status with its decisions", () => {
    render(<Trading />);
    for (const title of ["Proposées", "En position", "Sortie proposée", "Clôturées"]) {
      expect(screen.getByRole("heading", { name: new RegExp(title), hidden: true })).toBeInTheDocument();
    }
    expect(screen.getByText("AIR.PA")).toBeInTheDocument();
    expect(screen.getByText("Stop-loss franchi avec volume.")).toBeInTheDocument();
    expect(screen.getByText(/aucun ordre n'est passé/i)).toBeInTheDocument();
  });

  it("confirms a proposal sending only the adjusted level", () => {
    const m = mutation();
    useConfirmDecision.mockReturnValue(m);
    render(<Trading />);
    fireEvent.change(screen.getByLabelText("Stop-loss (€)"), { target: { value: "160,5" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmer", hidden: true }));
    expect(m.mutate).toHaveBeenCalledWith({ id: 1, takeProfit: undefined, stopLoss: 160.5 }, expect.anything());
  });

  it("blocks confirmation when a level is invalid", () => {
    render(<Trading />);
    fireEvent.change(screen.getByLabelText("Take-profit (€)"), { target: { value: "-3" } });
    expect(screen.getByRole("button", { name: "Confirmer", hidden: true })).toBeDisabled();
  });

  it("asks for a second click before closing a position", () => {
    const m = mutation();
    useConfirmExit.mockReturnValue(m);
    render(<Trading />);
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la sortie", hidden: true }));
    expect(m.mutate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Oui, clôturer", hidden: true }));
    expect(m.mutate).toHaveBeenCalledWith(2, expect.anything());
  });

  it("runs the monitoring job and reports how many exits were proposed", () => {
    const m = mutation();
    useMonitorDecisions.mockReturnValue(m);
    render(<Trading />);
    fireEvent.click(screen.getByRole("button", { name: "Surveiller les positions", hidden: true }));
    act(() => m.mutate.mock.calls[0][1].onSuccess([{ id: 9 }, { id: 10 }]));
    expect(screen.getByText("2 sortie(s) proposée(s).")).toBeInTheDocument();
  });
});
