import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import UniversRadar from "./UniversRadar";
import { buildRadar } from "./universRadarLayout";

const securities = [
  { symbol: "AIR.PA", name: "Airbus", sector: "Industrie" },
  { symbol: "SU.PA", name: "Schneider", sector: "Industrie" },
  { symbol: "SAF.PA", name: "Safran", sector: "Industrie" },
  { symbol: "HO.PA", name: "Thales", sector: "Industrie" },
  { symbol: "BNP.PA", name: "BNP Paribas", sector: "Finance" },
];

describe("buildRadar", () => {
  it("places every security once, biggest sector first, and labels only sectors with enough members", () => {
    const { items, labels } = buildRadar(securities, {}, {});
    expect(items.map((i) => i.symbol)).toEqual(["AIR.PA", "SU.PA", "SAF.PA", "HO.PA", "BNP.PA"]);
    expect(labels.map((l) => l.sector)).toEqual(["Industrie"]);
  });

  it("uses the real pattern confidence and leaves securities without a pattern bar-less", () => {
    const { items } = buildRadar(securities, { "AIR.PA": { confidence: 82.4 } }, {});
    expect(items.find((i) => i.symbol === "AIR.PA").confidence).toBeCloseTo(82.4);
    expect(items.find((i) => i.symbol === "SU.PA").confidence).toBeNull();
  });

  it("flags only exit-type decisions as 'lighten'", () => {
    const decisions = {
      "AIR.PA": { decision_type: "Achat" },
      "SU.PA": { decision_type: "Surveiller" },
      "SAF.PA": { decision_type: "Alléger" },
    };
    const { items } = buildRadar(securities, {}, decisions);
    const lighten = Object.fromEntries(items.map((i) => [i.symbol, i.lighten]));
    expect(lighten).toMatchObject({ "AIR.PA": false, "SU.PA": false, "SAF.PA": true, "HO.PA": false });
  });
});

describe("UniversRadar", () => {
  it("renders an accessible summary and selects a security on click", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <UniversRadar
        securities={securities}
        patternsBySymbol={{ "AIR.PA": { confidence: 70 } }}
        decisionsMap={{}}
        selectedSymbol="AIR.PA"
        onSelect={onSelect}
        closes={[100, 102, 101, 105]}
      />
    );
    const svg = container.querySelector("svg");
    expect(svg.getAttribute("aria-label")).toMatch(/5 valeurs/);
    expect(svg.getAttribute("aria-label")).toMatch(/1 avec une figure/);
    expect(svg.textContent).toContain("AIR.PA · 70 %");

    const hit = [...container.querySelectorAll("line")].find((l) => l.textContent.startsWith("BNP.PA"));
    fireEvent.click(hit);
    expect(onSelect).toHaveBeenCalledWith("BNP.PA");
  });

  it("does not crash without price history", () => {
    const { container } = render(
      <UniversRadar securities={securities} patternsBySymbol={{}} decisionsMap={{}} selectedSymbol={null} onSelect={() => {}} closes={[]} />
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
