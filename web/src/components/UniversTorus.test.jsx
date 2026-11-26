import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import UniversTorus from "./UniversTorus";
import { mockContainerWidth } from "../test/containerWidth";
import { buildCards, buildFilaments, makeProjector, MAX_RADIUS, nearestFilament, torusPoint } from "./torusLayout";
import { buildRadar } from "./universRadarLayout";

const securities = [
  { symbol: "AAA.PA", name: "Alpha", sector: "Santé" },
  { symbol: "BBB.PA", name: "Beta", sector: "Santé" },
  { symbol: "CCC.PA", name: "Gamma", sector: "Santé" },
];
const patterns = { "AAA.PA": { confidence: 80 } };
const decisions = { "AAA.PA": { symbol: "AAA.PA", decision_type: "Achat", entry_price: 10, created_at: "2026-11-20T10:00:00" } };
const filaments = () => buildFilaments(buildRadar(securities, patterns, decisions).items);
const radius = ([x, y, z]) => Math.hypot(x, y, z);

describe("torusLayout", () => {
  it("lengthens a spike with the pattern confidence", () => {
    const [withPattern, without] = filaments();
    expect(radius(withPattern.tip)).toBeGreaterThan(radius(without.tip));
    expect(radius(withPattern.tip)).toBeLessThanOrEqual(MAX_RADIUS);
  });

  it("keeps every spike inside the frame whatever the rotation", () => {
    const all = buildFilaments(buildRadar(securities, { "AAA.PA": { confidence: 100 } }, {}).items);
    for (let spin = 0; spin < 6.3; spin += 0.2) {
      const project = makeProjector({ spin, yaw: -0.7, tilt: 0.25, width: 600, height: 600 });
      for (const { tip } of all) {
        const { x, y } = project(tip);
        expect(Math.min(x, y)).toBeGreaterThanOrEqual(0);
        expect(Math.max(x, y)).toBeLessThanOrEqual(600);
      }
    }
  });

  it("spins around the axis going through the hole, which stays still", () => {
    const view = { yaw: -0.7, tilt: 0.25, width: 600, height: 600 };
    const still = makeProjector({ ...view, spin: 0 });
    const turned = makeProjector({ ...view, spin: 2 });
    expect(turned([0, 0, 0.5])).toEqual(still([0, 0, 0.5]));
    expect(turned(torusPoint(0, 0)).x).not.toBeCloseTo(still(torusPoint(0, 0)).x);
  });

  it("lists the latest decisions first and always keeps the selected security", () => {
    const map = {
      "AAA.PA": { symbol: "AAA.PA", created_at: "2026-11-01T10:00:00" },
      "BBB.PA": { symbol: "BBB.PA", created_at: "2026-11-20T10:00:00" },
      "ZZZ.PA": { symbol: "ZZZ.PA", created_at: "2026-11-25T10:00:00" },
    };
    const symbols = (cards) => cards.map((card) => card.symbol);
    expect(symbols(buildCards(filaments(), map, "AAA.PA"))).toEqual(["BBB.PA", "AAA.PA"]);
    expect(symbols(buildCards(filaments(), map, "CCC.PA", 2))).toEqual(["BBB.PA", "CCC.PA"]);
  });

  it("picks the spike under the pointer, and nothing far from every spike", () => {
    const all = filaments();
    const project = makeProjector({ yaw: 0, tilt: 0, width: 600, height: 600 });
    const { x, y } = project(all[1].tip);
    expect(nearestFilament(all, project, x + 3, y + 3).symbol).toBe("BBB.PA");
    expect(nearestFilament(all, project, 300, 300)).toBeNull();
  });
});

describe("UniversTorus", () => {
  const props = { securities, patternsBySymbol: patterns, decisionsMap: decisions, selectedSymbol: "AAA.PA" };

  beforeEach(() => {
    // jsdom ne dessine pas : un contexte factice suffit.
    const context = new Proxy({}, { get: (target, key) => (key in target ? target[key] : () => {}) });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("describes the data and the selected security", () => {
    render(<UniversTorus {...props} onSelect={() => {}} />);
    expect(screen.getByRole("img", { name: /3 valeurs, 1 avec une figure/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AAA\.PA.*Achat/, pressed: true })).toBeInTheDocument();
  });

  it("selects a security from its card, beside the torus or below it", () => {
    for (const width of [900, 360]) {
      mockContainerWidth(width);
      const onSelect = vi.fn();
      const { unmount } = render(<UniversTorus {...props} selectedSymbol="BBB.PA" onSelect={onSelect} />);
      fireEvent.click(screen.getByRole("button", { name: /AAA\.PA/ }));
      expect(onSelect).toHaveBeenCalledWith("AAA.PA");
      unmount();
    }
  });

  it("lets the user pause and restart the rotation", () => {
    render(<UniversTorus {...props} onSelect={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Mettre en pause" }));
    expect(screen.getByRole("button", { name: "Faire tourner" })).toBeInTheDocument();
  });

  it("does not start rotating when reduced motion is requested", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    render(<UniversTorus {...props} onSelect={() => {}} />);
    expect(screen.getByRole("button", { name: "Faire tourner" })).toBeInTheDocument();
  });

  it("selects on a click, ignoring a second finger", () => {
    const onSelect = vi.fn();
    const size = 360; // cadre étroit : le tore occupe tout le canvas
    mockContainerWidth(size);
    render(<UniversTorus {...props} onSelect={onSelect} />);
    const { x, y } = makeProjector({ yaw: -0.7, tilt: 0.25, width: size, height: size })(filaments()[1].tip);
    const canvas = screen.getByRole("img");
    // jsdom n'a pas de PointerEvent : on fixe les champs sur un MouseEvent.
    const fire = (type, pointerId) => {
      const event = new MouseEvent(type, { bubbles: true, button: 0, clientX: x, clientY: y });
      Object.defineProperty(event, "pointerId", { value: pointerId });
      fireEvent(canvas, event);
    };
    fire("pointerdown", 1);
    fire("pointerdown", 2);
    fire("pointerup", 2);
    expect(onSelect).not.toHaveBeenCalled();
    fire("pointerup", 1);
    expect(onSelect).toHaveBeenCalledWith("BBB.PA");
  });
});
