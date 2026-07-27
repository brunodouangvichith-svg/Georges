import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Paniers from "./Paniers";

vi.mock("../api/queries", () => ({
  useBaskets: vi.fn(),
  useSecurities: vi.fn(),
  useDecisions: vi.fn(),
  useGeorgeIndex: vi.fn(),
}));

import { useBaskets, useDecisions, useGeorgeIndex, useSecurities } from "../api/queries";

function mockEmptyApi() {
  useBaskets.mockReturnValue({ data: [], isLoading: false, isError: false });
  useSecurities.mockReturnValue({ data: { items: [] }, isError: false });
  useDecisions.mockReturnValue({ data: { items: [] }, isError: false });
  useGeorgeIndex.mockReturnValue({ data: null, isLoading: false });
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
});
