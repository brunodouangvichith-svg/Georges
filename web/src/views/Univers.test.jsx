import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { mockContainerWidth } from "../test/containerWidth";
import Univers from "./Univers";

vi.mock("../api/queries", () => ({
  useSecurities: vi.fn(),
  useSecurityDividends: vi.fn(),
  useSecurityFundamentals: vi.fn(),
  useSecurityPatterns: vi.fn(),
  useSecurityPrices: vi.fn(),
  useDecisions: vi.fn(),
  useAgentActivity: vi.fn(),
  useLatestPatterns: vi.fn(),
  useChat: vi.fn(),
  useRefreshPrices: vi.fn(),
  useRiskMetrics: vi.fn(),
  useTriggerCollection: vi.fn(),
}));

import {
  useAgentActivity,
  useChat,
  useDecisions,
  useLatestPatterns,
  useRefreshPrices,
  useRiskMetrics,
  useSecurities,
  useSecurityDividends,
  useSecurityFundamentals,
  useSecurityPatterns,
  useSecurityPrices,
  useTriggerCollection,
} from "../api/queries";

function mockEmptyApi() {
  useSecurities.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, isError: false });
  useDecisions.mockReturnValue({ data: { items: [], total: 0 } });
  useAgentActivity.mockReturnValue({ data: { items: [] } });
  useLatestPatterns.mockReturnValue({});
  useSecurityPatterns.mockReturnValue({ data: { items: [] } });
  useSecurityPrices.mockReturnValue({ data: { items: [], total: 0 } });
  useSecurityFundamentals.mockReturnValue({ data: undefined });
  useSecurityDividends.mockReturnValue({ data: { items: [], total: 0 } });
  useChat.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useRiskMetrics.mockReturnValue({ data: undefined, isLoading: false, isError: false });
  useRefreshPrices.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useTriggerCollection.mockReturnValue({ mutate: vi.fn(), isPending: false });
}

describe("Univers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockEmptyApi();
    // jsdom ne dessine pas : sans contexte, le tore ne trace rien.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  });

  it("shows an empty-state message when there are no securities in the database", () => {
    render(<Univers />);
    expect(screen.getByText(/aucun titre en base/i)).toBeInTheDocument();
  });

  it("shows a connection error message when the API is unreachable", () => {
    useSecurities.mockReturnValue({ data: undefined, isLoading: false, isError: true });
    render(<Univers />);
    expect(screen.getByText(/impossible de contacter l'api/i)).toBeInTheDocument();
  });

  it("lists securities returned by the API", () => {
    useSecurities.mockReturnValue({
      data: { items: [{ symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" }], total: 1 },
      isLoading: false,
      isError: false,
    });
    render(<Univers />);
    // La première valeur est sélectionnée d'office dans le panneau de détail.
    expect(screen.getByText("Airbus")).toBeInTheDocument();
  });

  it("draws the candlestick chart at the measured width of its frame, 320 px by default", () => {
    useSecurities.mockReturnValue({
      data: { items: [{ symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" }], total: 1 },
      isLoading: false,
      isError: false,
    });
    useSecurityPrices.mockReturnValue({ data: { items: [{ open: 1, high: 2, low: 1, close: 2 }], total: 1 } });
    const chartWidth = (container) => container.querySelector("svg[height='150']").getAttribute("width");

    const first = render(<Univers />);
    expect(chartWidth(first.container)).toBe("320");
    first.unmount();

    const spy = mockContainerWidth(290);
    expect(chartWidth(render(<Univers />).container)).toBe("290");
    spy.mockRestore();
  });

  it("shows the torus alone, with the selected security panel below it", () => {
    useSecurities.mockReturnValue({
      data: { items: [{ symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" }], total: 1 },
      isLoading: false,
      isError: false,
    });
    render(<Univers />);
    expect(screen.queryByRole("button", { name: /radar|tore 3d/i })).not.toBeInTheDocument();
    const torus = screen.getByRole("region", { name: "Tore 3D de l'univers" });
    const panel = screen.getByRole("region", { name: "Valeur sélectionnée" });
    expect(torus.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows the risk measures of the selected security only", () => {
    useSecurities.mockReturnValue({
      data: {
        items: [
          { symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" },
          { symbol: "TTE.PA", name: "TotalEnergies", sector: "Énergie" },
        ],
        total: 2,
      },
      isLoading: false,
      isError: false,
    });
    useRiskMetrics.mockReturnValue({
      data: {
        index: { name: "CAC 40", available: true, as_of: "2026-11-25" },
        items: [
          { symbol: "AIR.PA", beta: 1.11, sector_peers: 0 },
          { symbol: "TTE.PA", beta: 0.77, sector_peers: 0 },
        ],
      },
    });
    render(<Univers />);
    expect(screen.getByText("1,11")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Choisir une valeur" }), { target: { value: "TTE.PA" } });
    expect(screen.getByText("0,77")).toBeInTheDocument();
    expect(screen.queryByText("1,11")).not.toBeInTheDocument();
  });

  it("keeps the measures already shown when a background refresh fails", () => {
    useSecurities.mockReturnValue({
      data: { items: [{ symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" }], total: 1 },
      isLoading: false,
      isError: false,
    });
    useRiskMetrics.mockReturnValue({
      data: { index: { name: "CAC 40", available: false }, items: [{ symbol: "AIR.PA", beta: 1.11 }] },
      isError: true,
    });
    render(<Univers />);
    expect(screen.getByText("1,11")).toBeInTheDocument();
  });

  it("changes the selected security from the dropdown, sorted by name", () => {
    useSecurities.mockReturnValue({
      data: {
        items: [
          { symbol: "TTE.PA", name: "TotalEnergies", sector: "Énergie" },
          { symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" },
        ],
        total: 2,
      },
      isLoading: false,
      isError: false,
    });
    render(<Univers />);
    const select = screen.getByLabelText("Choisir une valeur");
    expect([...select.options].map((o) => o.value)).toEqual(["AIR.PA", "TTE.PA"]);
    fireEvent.change(select, { target: { value: "AIR.PA" } });
    expect(select).toHaveValue("AIR.PA");
    expect(screen.getByText("Airbus")).toBeInTheDocument();
  });

  it("only shows Univers in the sidebar navigation, without Paniers/Décisions/George Index/Historique", () => {
    render(<Univers />);
    expect(screen.getByText("Univers")).toBeInTheDocument();
    expect(screen.queryByText("Paniers")).not.toBeInTheDocument();
    expect(screen.queryByText("Décisions")).not.toBeInTheDocument();
    expect(screen.queryByText("George Index")).not.toBeInTheDocument();
    expect(screen.queryByText("Historique")).not.toBeInTheDocument();
  });

  it("triggers a price refresh and shows the result summary when the sidebar button is clicked", () => {
    const mutate = vi.fn();
    useRefreshPrices.mockReturnValue({ mutate, isPending: false });
    render(<Univers />);

    fireEvent.click(screen.getByText("Mise à jour des prix"));
    expect(mutate).toHaveBeenCalled();

    const onSuccess = mutate.mock.calls[0][1].onSuccess;
    act(() => onSuccess({ total: 102, updated_count: 100, failed_symbols: ["XYZ.PA", "ABC.PA"] }));
    expect(screen.getByText(/100\/102 titres mis à jour/)).toBeInTheDocument();
    expect(screen.getByText(/Échecs : XYZ\.PA, ABC\.PA/)).toBeInTheDocument();
  });

  it("triggers a macro collection and shows the validated/quarantined summary when clicked", () => {
    const mutate = vi.fn();
    useTriggerCollection.mockReturnValue({ mutate, isPending: false });
    render(<Univers />);

    fireEvent.click(screen.getByText("Collecte macro"));
    expect(mutate).toHaveBeenCalledWith("donnees_macro", expect.anything());

    const onSuccess = mutate.mock.calls[0][1].onSuccess;
    act(() => onSuccess({ validated: [{}, {}], quarantined_count: 1 }));
    expect(screen.getByText(/2 validée\(s\), 1 en quarantaine/)).toBeInTheDocument();
  });
});
