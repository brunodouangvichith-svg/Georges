// `hidden: true` sur les getByRole : contourne le même bug de jsdom 30 que
// Obligataire.test.jsx (getComputedStyle plante sur certains styles inline).
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Trading from "./Trading";

vi.mock("../api/queries", () => ({
  useStrategicReport: vi.fn(),
}));

import { useStrategicReport } from "../api/queries";

describe("Trading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useStrategicReport.mockReturnValue({ data: null, isLoading: false, isError: false });
  });

  it("shows neither lifecycle columns, performance nor job buttons", () => {
    render(<Trading />);
    for (const title of ["Proposées", "En position", "Sortie proposée", "Clôturées", "Performance réalisée"]) {
      expect(screen.queryByRole("heading", { name: new RegExp(title), hidden: true })).not.toBeInTheDocument();
    }
    for (const name of ["Lancer une détection", "Surveiller les positions"]) {
      expect(screen.queryByRole("button", { name, hidden: true })).not.toBeInTheDocument();
    }
    expect(screen.getByText(/aucun ordre n'est passé/i)).toBeInTheDocument();
  });

  it("shows the CAC 40 stocks from the latest strategic report", () => {
    useStrategicReport.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        created_at: "2026-10-16T09:00:00Z",
        data: {
          cac40: [
            { symbol: "AIR.PA", name: "Airbus", sector: "Industrie", close: 198.75, week_change_pct: 2.1, decision_type: "Achat", confidence: 80, pattern_type: "Double Bottom" },
            { symbol: "MC.PA", name: "LVMH", sector: "Luxe", close: 396, week_change_pct: -3, decision_type: null, confidence: null, pattern_type: null },
          ],
        },
      },
    });
    render(<Trading />);
    expect(useStrategicReport).toHaveBeenCalledWith(null);
    expect(screen.getByRole("heading", { name: "Valeurs du CAC 40 (2)", hidden: true })).toBeInTheDocument();
    expect(screen.getByText("LVMH")).toBeInTheDocument();
    expect(screen.getByText(/16 octobre 2026/)).toBeInTheDocument();
  });

  it("says when no strategic report exists for the CAC 40 table", () => {
    render(<Trading />);
    expect(screen.getByText(/génère un rapport dans l'onglet « Rapport »/)).toBeInTheDocument();
  });
});
