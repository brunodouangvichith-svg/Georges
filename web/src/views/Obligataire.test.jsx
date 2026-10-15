import { act, fireEvent, render, screen } from "@testing-library/react";
// `hidden: true` sur les getByRole des seuils : contourne un bug de jsdom 30
// (getComputedStyle plante sur certains styles inline), sans effet sur ce qui
// est vérifié — ces boutons sont bien visibles.
import { beforeEach, describe, expect, it, vi } from "vitest";
import Obligataire from "./Obligataire";

vi.mock("../api/queries", () => ({
  useBondDashboard: vi.fn(),
  useBondHistory: vi.fn(),
  useBondThresholds: vi.fn(),
  useBondAlertEvents: vi.fn(),
  useBondCollectionRuns: vi.fn(),
  useBondBulletin: vi.fn(),
  useUpdateBondThreshold: vi.fn(),
  useRefreshBonds: vi.fn(),
}));

import {
  useBondAlertEvents,
  useBondBulletin,
  useBondCollectionRuns,
  useBondDashboard,
  useBondHistory,
  useBondThresholds,
  useRefreshBonds,
  useUpdateBondThreshold,
} from "../api/queries";

const emptyVariations = { "24h": null, "7j": null, "30j": null };
const dashboard = {
  cards: [
    { instrument: "OAT_FR_10Y", value_pct: 3.41, observed_at: "2026-09-01", fetched_at: "2026-10-15T07:00:00Z", source_name: "FRED", source_url: null, variations_bps: { "24h": null, "7j": 4, "30j": -12 } },
    { instrument: "BUND_DE_10Y", value_pct: null, observed_at: null, fetched_at: null, source_name: null, source_url: null, variations_bps: emptyVariations },
  ],
  spread_oat_bund_bps: 72,
  us_curve_slope_bps: -15,
};
const thresholds = [{ id: 7, instrument: "OAT_FR_10Y", direction: "above", threshold_pct: 4.9, enabled: true, updated_at: "2026-10-01T00:00:00Z" }];

function mockApi() {
  useBondDashboard.mockReturnValue({ data: dashboard, isLoading: false, isError: false });
  useBondHistory.mockReturnValue({ data: [], isLoading: false });
  useBondThresholds.mockReturnValue({ data: thresholds });
  useBondAlertEvents.mockReturnValue({ data: [] });
  useBondCollectionRuns.mockReturnValue({ data: [] });
  useBondBulletin.mockReturnValue({ data: { bulletin: "BULLETIN OBLIGATAIRE QUOTIDIEN", generated_at: "2026-10-15T07:00:00Z" }, isLoading: false });
  useUpdateBondThreshold.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useRefreshBonds.mockReturnValue({ mutate: vi.fn(), isPending: false });
}

describe("Obligataire", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi();
  });

  it("shows real yields, variations, spreads and an explicit unavailable state", () => {
    render(<Obligataire />);
    expect(screen.getByText("3.41 %")).toBeInTheDocument();
    expect(screen.getByText(/donnée indisponible/i)).toBeInTheDocument();
    expect(screen.getByText("+72 pb")).toBeInTheDocument();
    expect(screen.getByText("-15 pb")).toBeInTheDocument();
    expect(screen.getByText(/24h n\/d/)).toBeInTheDocument();
    expect(screen.getByText("BULLETIN OBLIGATAIRE QUOTIDIEN")).toBeInTheDocument();
  });

  it("only sends the changed field when a threshold is edited", () => {
    const mutate = vi.fn();
    useUpdateBondThreshold.mockReturnValue({ mutate, isPending: false });
    render(<Obligataire />);

    const save = screen.getByRole("button", { name: "Enregistrer", hidden: true });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/OAT France 10 ans/), { target: { value: "5,1" } });
    fireEvent.click(save);
    expect(mutate).toHaveBeenCalledWith({ id: 7, thresholdPct: 5.1, enabled: undefined }, expect.anything());
  });

  it("refuses an invalid threshold value", () => {
    render(<Obligataire />);
    fireEvent.change(screen.getByLabelText(/OAT France 10 ans/), { target: { value: "abc" } });
    expect(screen.getByRole("button", { name: "Enregistrer", hidden: true })).toBeDisabled();
  });

  it("runs a manual collection and shows its summary", () => {
    const mutate = vi.fn();
    useRefreshBonds.mockReturnValue({ mutate, isPending: false });
    render(<Obligataire />);
    fireEvent.click(screen.getByRole("button", { name: "Mettre à jour les taux" }));
    act(() => mutate.mock.calls[0][1].onSuccess({ instruments_updated: ["OAT_FR_10Y", "UST_US_10Y"], instruments_failed: ["BUND_DE_10Y"], alerts_created: 1 }));
    expect(screen.getByText(/2 série\(s\) mise\(s\) à jour, 1 nouvelle\(s\) alerte\(s\)\. Échecs : Bund Allemagne 10 ans\./)).toBeInTheDocument();
  });
});
