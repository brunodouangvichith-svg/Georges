import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Gauge from "./Gauge";

describe("Gauge", () => {
  it("displays the numeric value", () => {
    render(<Gauge value={77} color="green" />);
    expect(screen.getByText("77")).toBeInTheDocument();
  });
});
