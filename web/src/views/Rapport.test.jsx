import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Rapport from "./Rapport";

vi.mock("../api/queries", () => ({
  useStrategicReports: vi.fn(),
  useStrategicReport: vi.fn(),
  useGenerateStrategicReport: vi.fn(),
  useBondDashboard: vi.fn(),
}));

import { useBondDashboard, useGenerateStrategicReport, useStrategicReport, useStrategicReports } from "../api/queries";

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
    cac40: [
      { symbol: "AIR.PA", name: "Airbus", sector: "Industrie", close: 198.75, week_change_pct: 2.1, decision_type: "Achat", confidence: 80, pattern_type: "Double Bottom" },
      { symbol: "MC.PA", name: "LVMH", sector: "Luxe", close: 396, week_change_pct: -3, decision_type: null, confidence: null, pattern_type: null },
    ],
    sources: [{ n: 1, theme: "Croissance, emploi, inflation", titre: "Inflation en septembre", url: "https://www.insee.fr/x" }],
  },
};

function setup({ reportData = report, list = [{ id: 3, created_at: report.created_at, risk_level: "orange" }], mutate = vi.fn(), pending = false, bonds, bondsError = false } = {}) {
  useBondDashboard.mockReturnValue({ data: bonds, isError: bondsError });
  useStrategicReports.mockReturnValue({ data: list });
  useStrategicReport.mockReturnValue({ data: reportData, isLoading: false, isError: false });
  useGenerateStrategicReport.mockReturnValue({ mutate, isPending: pending, isError: false });
  return render(<Rapport />);
}

const bonds = (value_pct, spread, bundDate = "2026-10-23", oatDate = "2026-10-23") => ({
  cards: [
    { instrument: "OAT_FR_10Y", value_pct, observed_at: oatDate },
    { instrument: "BUND_DE_10Y", value_pct: 3.44, observed_at: bundDate },
  ],
  spread_oat_bund_bps: spread,
});

describe("Rapport", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the risk level, key figures, the commentary with linked sources, without the CAC 40 table", () => {
    setup();
    expect(screen.getByText("ORANGE")).toBeInTheDocument();
    expect(screen.getByText("7 934,70")).toBeInTheDocument();
    expect(screen.getByText("+140 pb")).toBeInTheDocument();
    expect(screen.getByText("3,1 %")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1]", hidden: true })).toHaveAttribute("href", "#source-1");
    expect(screen.getByRole("link", { name: "Inflation en septembre", hidden: true })).toHaveAttribute("href", "https://www.insee.fr/x");
    expect(screen.queryByText("LVMH")).not.toBeInTheDocument();
  });

  it("recalls the current bond values only when they differ from the report", () => {
    const { unmount } = setup({ bonds: bonds(4.9, 140.2) });
    expect(screen.queryByText(/Valeur actuelle/)).not.toBeInTheDocument();
    unmount();
    setup({ bonds: bonds(4.62, 118) });
    expect(screen.getByText("4,90 %")).toBeInTheDocument();
    expect(screen.getByText(/Valeur actuelle : 4,62 % au 23 octobre 2026/)).toBeInTheDocument();
    expect(screen.getByText(/Valeur actuelle : \+118 pb au 23 octobre 2026/)).toBeInTheDocument();
  });

  it("dates both legs of the recalled spread when they differ", () => {
    setup({ bonds: bonds(4.62, 118, "2026-10-02") });
    expect(screen.getByText(/\+118 pb \(OAT au 23 octobre 2026, Bund au 02 octobre 2026\)/)).toBeInTheDocument();
  });

  it("never presents values older than the report as current", () => {
    setup({ bonds: bonds(4.62, 118, "2026-08-01", "2026-08-01") });
    expect(screen.queryByText(/Valeur actuelle/)).not.toBeInTheDocument();
  });

  it("says the current values are unavailable when the bond request fails", () => {
    setup({ bonds: bonds(4.62, 118), bondsError: true });
    expect(screen.getAllByText(/Valeur actuelle : indisponible/)).toHaveLength(2);
    expect(screen.queryByText(/4,62 %/)).not.toBeInTheDocument();
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
