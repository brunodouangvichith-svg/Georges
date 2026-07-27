import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import Univers from "./Univers";

vi.mock("../api/queries", () => ({
  useSecurities: vi.fn(),
  useSecurityPatterns: vi.fn(),
  useSecurityPrices: vi.fn(),
  useBaskets: vi.fn(),
  useGeorgeIndex: vi.fn(),
  useDecisions: vi.fn(),
  useAgentActivity: vi.fn(),
  useChat: vi.fn(),
  useExplainDecision: vi.fn(),
}));

import {
  useAgentActivity,
  useBaskets,
  useChat,
  useDecisions,
  useExplainDecision,
  useGeorgeIndex,
  useSecurities,
  useSecurityPatterns,
  useSecurityPrices,
} from "../api/queries";

function mockEmptyApi() {
  useSecurities.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, isError: false });
  useDecisions.mockReturnValue({ data: { items: [], total: 0 } });
  useBaskets.mockReturnValue({ data: [] });
  useAgentActivity.mockReturnValue({ data: { items: [] } });
  useSecurityPatterns.mockReturnValue({ data: { items: [] } });
  useSecurityPrices.mockReturnValue({ data: { items: [], total: 0 } });
  useGeorgeIndex.mockReturnValue({ data: null, isLoading: false });
  useChat.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useExplainDecision.mockReturnValue({ mutate: vi.fn(), isPending: false });
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
});
