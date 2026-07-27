import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Sparkline from "./Sparkline";

describe("Sparkline", () => {
  it("renders a polyline with one point per value", () => {
    const { container } = render(<Sparkline points={[1, 5, 2, 8, 3]} color="red" width={90} height={28} />);
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeInTheDocument();
    expect(polyline.getAttribute("points").trim().split(" ")).toHaveLength(5);
  });

  it("does not divide by zero when every value is identical", () => {
    const { container } = render(<Sparkline points={[4, 4, 4]} color="blue" />);
    const points = container.querySelector("polyline").getAttribute("points");
    expect(points).not.toMatch(/NaN|Infinity/);
  });
});
