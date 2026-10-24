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

  it("groups sub-sectors by family and puts small families in 'Autres secteurs'", () => {
    const secs = [
      { symbol: "A", name: "a", sector: "Santé / Biotechnologie" },
      { symbol: "B", name: "b", sector: "Santé / Pharmacie" },
      { symbol: "C", name: "c", sector: "Santé" },
      { symbol: "D", name: "d", sector: "Énergie / Utilities" },
      { symbol: "E", name: "e", sector: "Médias" },
      { symbol: "F", name: "f", sector: "Assurance" },
    ];
    const { items, labels } = buildRadar(secs, {}, {});
    expect(labels.map((l) => l.sector)).toEqual(["Santé", "Autres secteurs"]);
    expect(items.map((i) => i.symbol)).toEqual(["A", "B", "C", "D", "E", "F"]);
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

  it("orients sector labels along the radius so neighbours never overlap", () => {
    // ~100 valeurs dans 12 secteurs, dont plusieurs petits voisins (cas réel
    // où "SANTÉ / BIOTECH" et "SERVICES" se chevauchaient en haut du cercle).
    const sizes = [18, 14, 12, 10, 9, 8, 7, 6, 5, 5, 4, 4];
    const many = sizes.flatMap((n, i) =>
      Array.from({ length: n }, (_, j) => ({ symbol: `S${i}-${j}`, name: "x", sector: `Secteur numéro ${i}` })),
    );
    const { labels } = buildRadar(many, {}, {});
    expect(labels).toHaveLength(sizes.length);
    const angles = labels.map((l) => Math.atan2(l.y - 340, l.x - 380)).sort((a, b) => a - b);
    const gaps = angles.map((a, i) => (i === 0 ? a + 2 * Math.PI - angles.at(-1) : a - angles[i - 1]));
    // Police de 10,5 px au rayon ~212 : ~3° suffisent ; on exige plus de 6°.
    expect(Math.min(...gaps)).toBeGreaterThan((6 * Math.PI) / 180);
    for (const l of labels) {
      expect(l.rotate).toBeGreaterThanOrEqual(-90);
      expect(l.rotate).toBeLessThanOrEqual(90); // jamais à l'envers
    }
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
