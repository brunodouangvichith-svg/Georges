import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import Univers from "./Univers";

vi.mock("../api/queries", () => ({
  useSecurities: vi.fn(),
  useSecurityDividends: vi.fn(),
  useSecurityFundamentals: vi.fn(),
  useSecurityPatterns: vi.fn(),
  useSecurityPrices: vi.fn(),
  useBaskets: vi.fn(),
  useGeorgeIndex: vi.fn(),
  useDecisions: vi.fn(),
  useAgentActivity: vi.fn(),
  useChat: vi.fn(),
  useExplainDecision: vi.fn(),
  useRefreshPrices: vi.fn(),
  useTriggerCollection: vi.fn(),
}));

import {
  useAgentActivity,
  useBaskets,
  useChat,
  useDecisions,
  useExplainDecision,
  useGeorgeIndex,
  useRefreshPrices,
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
  useBaskets.mockReturnValue({ data: [] });
  useAgentActivity.mockReturnValue({ data: { items: [] } });
  useSecurityPatterns.mockReturnValue({ data: { items: [] } });
  useSecurityPrices.mockReturnValue({ data: { items: [], total: 0 } });
  useSecurityFundamentals.mockReturnValue({ data: undefined });
  useSecurityDividends.mockReturnValue({ data: { items: [], total: 0 } });
  useGeorgeIndex.mockReturnValue({ data: null, isLoading: false });
  useChat.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useExplainDecision.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useRefreshPrices.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useTriggerCollection.mockReturnValue({ mutate: vi.fn(), isPending: false });
}

describe("Univers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockEmptyApi();
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
    expect(screen.getByText("AIR.PA")).toBeInTheDocument();
    // "Airbus" apparaît à la fois dans la ligne de la watchlist et dans le
    // panneau de détail (la première valeur est auto-sélectionnée).
    expect(screen.getAllByText("Airbus").length).toBeGreaterThan(0);
  });

  it("invites the user to ask George when no decision exists for the selected security", () => {
    useSecurities.mockReturnValue({
      data: { items: [{ symbol: "AIR.PA", name: "Airbus", sector: "Aéronautique" }], total: 1 },
      isLoading: false,
      isError: false,
    });
    render(<Univers />);
    expect(screen.getByText(/posez une question à george/i)).toBeInTheDocument();
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
