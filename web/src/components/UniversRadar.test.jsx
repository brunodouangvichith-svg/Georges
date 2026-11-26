import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockContainerWidth } from "../test/containerWidth";
import UniversRadar from "./UniversRadar";
import { buildRadar, compactLabels, nearestItem, CX, CY, R_IN, R_TICK_OUT } from "./universRadarLayout";

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

describe("compactLabels / nearestItem", () => {
  const sizes = [18, 14, 12, 10, 9, 8, 7, 6, 5, 5, 4, 4];
  const many = sizes.flatMap((n, i) =>
    Array.from({ length: n }, (_, j) => ({ symbol: `S${i}-${j}`, name: "x", sector: `Secteur numéro ${i}` })),
  );
  const { items, labels } = buildRadar(many, {}, {});

  it.each([280, 320, 360, 499])("keeps readable, non-overlapping sector labels at %i px", (px) => {
    const scale = px / 760;
    const compact = compactLabels(labels, scale);
    expect(compact.fontSize * scale).toBeGreaterThanOrEqual(10.9);
    expect(compact.labels[0].sector).toBe(labels[0].sector); // le plus gros reste
    expect(compact.labels.length).toBeGreaterThanOrEqual(5);
    for (const a of compact.labels) {
      expect(a.text.length * 0.62 * compact.fontSize).toBeLessThanOrEqual(140);
      for (const b of compact.labels) {
        if (a === b) continue;
        // À l'extrémité intérieure, au moins une hauteur de police d'écart.
        const inner = 236 * 0.9 - Math.max(a.text.length, b.text.length) * 0.62 * compact.fontSize;
        const d = Math.abs(Math.atan2(Math.sin(a.angle - b.angle), Math.cos(a.angle - b.angle)));
        expect(d * inner).toBeGreaterThanOrEqual(compact.fontSize);
      }
    }
  });

  it("shows every label again once zoomed enough", () => {
    const compact = compactLabels(labels, 2);
    expect(compact.fontSize).toBe(10.5);
    expect(compact.labels).toHaveLength(labels.length);
  });

  it("picks the nearest security around the ring and nothing in the centre or corners", () => {
    const scale = 320 / 760;
    for (const item of [items[0], items[40], items.at(-1)]) {
      const a = item.angle + 0.005;
      const hit = nearestItem(items, CX + Math.cos(a) * (R_TICK_OUT + 20), CY + Math.sin(a) * (R_TICK_OUT + 20), scale);
      expect(hit.symbol).toBe(item.symbol);
    }
    expect(nearestItem(items, CX, CY, scale)).toBeNull();
    expect(nearestItem(items, CX + R_IN / 2, CY, scale)).toBeNull();
    expect(nearestItem(items, 0, 0, scale)).toBeNull();
    expect(nearestItem([], CX, CY - R_TICK_OUT, scale)).toBeNull();
  });
});

describe("UniversRadar", () => {
  afterEach(() => vi.restoreAllMocks());

  it("on a narrow screen, selects the security nearest to the tapped point, even zoomed", () => {
    mockContainerWidth(320);
    const onSelect = vi.fn();
    const { container } = render(
      <UniversRadar securities={securities} patternsBySymbol={{}} decisionsMap={{}} selectedSymbol="AIR.PA" onSelect={onSelect} closes={[]} />
    );
    const svg = container.querySelector("svg");
    svg.getBoundingClientRect = () => ({ left: 10, top: 20, width: 380, height: 340 });
    expect(container.querySelectorAll("line")).toHaveLength(0);
    // Le libellé de la sélection passe sous le radar.
    expect(container.querySelector("p").textContent).toBe("AIR.PA · sans figure");
    expect(svg.textContent).not.toContain("AIR.PA");

    const bnp = buildRadar(securities, {}, {}).items.find((i) => i.symbol === "BNP.PA");
    const x = CX + Math.cos(bnp.angle) * R_TICK_OUT;
    const y = CY + Math.sin(bnp.angle) * R_TICK_OUT;
    fireEvent.click(svg, { clientX: 10 + x / 2, clientY: 20 + y / 2 });
    expect(onSelect).toHaveBeenLastCalledWith("BNP.PA");

    // Zoom ×2 centré (viewBox 190 170 380 340) : un point de l'anneau reste juste.
    fireEvent.touchStart(svg, { touches: [{ clientX: 150, clientY: 190 }, { clientX: 250, clientY: 190 }] });
    fireEvent.touchMove(svg, { touches: [{ clientX: 100, clientY: 190 }, { clientX: 300, clientY: 190 }] });
    expect(svg.getAttribute("viewBox")).toBe("190 170 380 340");
    onSelect.mockClear();
    const air = buildRadar(securities, {}, {}).items[0]; // en haut du cercle
    const right = buildRadar(securities, {}, {}).items.find((i) => Math.cos(i.angle) > 0.5);
    const rx = CX + Math.cos(right.angle) * R_TICK_OUT;
    const ry = CY + Math.sin(right.angle) * R_TICK_OUT;
    fireEvent.click(svg, { clientX: 10 + (rx - 190), clientY: 20 + (ry - 170) });
    expect(onSelect).toHaveBeenLastCalledWith(right.symbol);
    expect(right.symbol).not.toBe(air.symbol);
  });

  it("keeps the wide rendering from 500 px up", () => {
    mockContainerWidth(500);
    const { container } = render(
      <UniversRadar securities={securities} patternsBySymbol={{}} decisionsMap={{}} selectedSymbol="AIR.PA" onSelect={() => {}} closes={[]} />
    );
    expect(container.querySelectorAll("line")).toHaveLength(securities.length);
    expect(container.querySelector("p")).toBeNull();
    expect(container.querySelector("svg").textContent).toContain("INDUSTRIE");
  });

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

  it("zooms with two fingers, pans with one, and returns to the full view", () => {
    const { container, queryByRole, getByRole } = render(
      <UniversRadar securities={securities} patternsBySymbol={{}} decisionsMap={{}} selectedSymbol={null} onSelect={() => {}} closes={[]} />
    );
    const svg = container.querySelector("svg");
    svg.getBoundingClientRect = () => ({ left: 0, top: 0, width: 380, height: 340 });
    const at = (...points) => ({ touches: points.map(([clientX, clientY]) => ({ clientX, clientY })) });

    // En vue entière, un doigt laisse la page défiler (événement non annulé).
    fireEvent.touchStart(svg, at([100, 100]));
    expect(fireEvent.touchMove(svg, at([100, 40]))).toBe(true);
    expect(svg.getAttribute("viewBox")).toBe("0 0 760 680");

    // Écartement doublé autour du centre : zoom ×2, centre inchangé.
    fireEvent.touchStart(svg, at([140, 170], [240, 170]));
    expect(fireEvent.touchMove(svg, at([90, 170], [290, 170]))).toBe(false);
    expect(svg.getAttribute("viewBox")).toBe("190 170 380 340");
    expect(svg.style.touchAction).toBe("none");

    // Un doigt déplace la vue agrandie, sans dépasser les bords.
    fireEvent.touchEnd(svg, at([90, 170]));
    fireEvent.touchMove(svg, at([140, 170]));
    expect(svg.getAttribute("viewBox")).toBe("140 170 380 340");
    fireEvent.touchMove(svg, at([900, 900]));
    expect(svg.getAttribute("viewBox")).toBe("0 0 380 340");

    fireEvent.click(getByRole("button", { name: "Vue entière" }));
    expect(svg.getAttribute("viewBox")).toBe("0 0 760 680");
    expect(queryByRole("button", { name: "Vue entière" })).toBeNull();
  });

  it("does not crash without price history", () => {
    const { container } = render(
      <UniversRadar securities={securities} patternsBySymbol={{}} decisionsMap={{}} selectedSymbol={null} onSelect={() => {}} closes={[]} />
    );
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
