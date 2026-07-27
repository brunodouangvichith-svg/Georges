import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import GeorgeIndexTile from "./GeorgeIndexTile";

vi.mock("../api/queries", () => ({
  useGeorgeIndex: vi.fn(),
}));

import { useGeorgeIndex } from "../api/queries";

describe("GeorgeIndexTile", () => {
  it("shows the rounded score when a pattern is active", () => {
    useGeorgeIndex.mockReturnValue({ data: { george_index: 77.4 }, isLoading: false });
    render(<GeorgeIndexTile basketId={1} basketName="Tech FR" />);
    expect(screen.getByText("Tech FR")).toBeInTheDocument();
    expect(screen.getByText("77")).toBeInTheDocument();
  });

  it("explains that the index is undefined when no pattern is active", () => {
    useGeorgeIndex.mockReturnValue({ data: { george_index: null }, isLoading: false });
    render(<GeorgeIndexTile basketId={1} basketName="Tech FR" />);
    expect(screen.getByText(/aucune figure active/i)).toBeInTheDocument();
  });
});
