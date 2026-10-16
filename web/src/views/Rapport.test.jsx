import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Rapport from "./Rapport";

vi.mock("../api/queries", () => ({
  useStrategicReports: vi.fn(),
  useStrategicReport: vi.fn(),
  useGenerateStrategicReport: vi.fn(),
}));

import { useGenerateStrategicReport, useStrategicReport, useStrategicReports } from "../api/queries";

const report = {
  id: 3,
  created_at: "2026-10-16T09:00:00Z",
  risk_level: "orange",
  model_used: "mistral-large-latest",
  narrative_markdown: "## Synthèse exécutive\n\n- L'inflation atteint **3,1 %** [1].",
  data: {
    generated_at: "2026-10-16T09:00:00Z",
    prices_as_of: "2026-10-15",
    risk: {
      level: "orange",
      oat_10y_pct: 4.9,
      oat_observed_at: "2026-09-01",
      bund_10y_pct: 3.5,
      spread_oat_bund_bps: 140,
      criteria: { rouge: "OAT > 5 % et spread > 150 pb", vert: "spread < 120 pb et OAT < 4,5 %", orange: "entre les deux" },
    },
    cac40_index: { close: 7934.7, as_of: "2026-10-15", week_change_pct: 1.68 },
    energy: [{ code: "BRENT_CRUDE_USD", price: 106, as_of: "2026-10-16", change_24h_pct: 1.4 }],
    portfolio: {
      initial_capital: 100000,
      fee_rate: 0.0015,
      min_cash_ratio: 0.45,
      cash: 92036.0,
      positions_value: 7950,
      total_value: 99986.0,
      fees_total: 11.93,
      performance_since_start_pct: -0.01,
      previous_total_value: null,
      performance_since_previous_pct: null,
      positions: [{ symbol: "AIR.PA", name: "Airbus", quantity: 40, price: 198.75, value: 7950, weight_pct: 7.95 }],
      trades: [{ symbol: "AIR.PA", name: "Airbus", side: "achat", quantity: 40, price: 198.75, gross: 7950, fees: 11.93, rationale: "Signal George « Achat » (confiance 80 %)" }],
    },
    cac40: [
      { symbol: "AIR.PA", name: "Airbus", sector: "Industrie", close: 198.75, week_change_pct: 2.1, decision_type: "Achat", confidence: 80, pattern_type: "Double Bottom", portfolio_action: "Achat simulé(e) : 40" },
      { symbol: "MC.PA", name: "LVMH", sector: "Luxe", close: 396, week_change_pct: -3, decision_type: null, confidence: null, pattern_type: null, portfolio_action: null },
    ],
    sources: [{ n: 1, theme: "Croissance, emploi, inflation", titre: "Inflation en septembre", url: "https://www.insee.fr/x" }],
  },
};

function setup({ reportData = report, list = [{ id: 3, created_at: report.created_at, risk_level: "orange" }], mutate = vi.fn(), pending = false } = {}) {
  useStrategicReports.mockReturnValue({ data: list });
  useStrategicReport.mockReturnValue({ data: reportData, isLoading: false, isError: false });
  useGenerateStrategicReport.mockReturnValue({ mutate, isPending: pending, isError: false });
  return render(<Rapport />);
}

describe("Rapport", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the risk level, key figures, the commentary with linked sources and the portfolio", () => {
    setup();
    expect(screen.getByText("ORANGE")).toBeInTheDocument();
    expect(screen.getByText("7 934,70")).toBeInTheDocument();
    expect(screen.getByText("+140 pb")).toBeInTheDocument();
    expect(screen.getByText("3,1 %")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1]", hidden: true })).toHaveAttribute("href", "#source-1");
    expect(screen.getByRole("link", { name: "Inflation en septembre", hidden: true })).toHaveAttribute("href", "https://www.insee.fr/x");
    expect(screen.getByText("Signal George « Achat » (confiance 80 %)")).toBeInTheDocument();
    expect(screen.getByText("LVMH")).toBeInTheDocument();
    expect(screen.getByText("Premier rapport")).toBeInTheDocument();
  });

  it("shows an empty state and starts a generation", () => {
    const mutate = vi.fn();
    setup({ reportData: null, list: [], mutate });
    expect(screen.getByText(/Aucun rapport n'a encore été généré/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Générer le rapport de la semaine", hidden: true }));
    expect(mutate).toHaveBeenCalledTimes(1);
  });

  it("disables the button while a report is being generated", () => {
    setup({ pending: true });
    expect(screen.getByRole("button", { name: /Génération…/, hidden: true })).toBeDisabled();
  });
});
