import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import UniversTorus from "./UniversTorus";
import { mockContainerWidth } from "../test/containerWidth";
import { buildCards, buildFilaments, buildItems, makeProjector, MAX_RADIUS, nearestFilament, torusPoint } from "./torusLayout";

const securities = [
  { symbol: "AAA.PA", name: "Alpha", sector: "Santé" },
  { symbol: "BBB.PA", name: "Beta", sector: "Santé" },
  { symbol: "CCC.PA", name: "Gamma", sector: "Santé" },
];
const patterns = { "AAA.PA": { confidence: 80 } };
const decisions = { "AAA.PA": { symbol: "AAA.PA", decision_type: "Achat", entry_price: 10, created_at: "2026-11-20T10:00:00" } };
const filaments = () => buildFilaments(buildItems(securities, patterns, decisions));
const radius = ([x, y, z]) => Math.hypot(x, y, z);

describe("torusLayout", () => {
  it("orders securities by sector family, biggest first, small families last", () => {
    const sectors = ["Médias", "Santé / Biotechnologie", "Énergie", "Santé / Pharmacie", "Énergie", "Santé", "Énergie", "Santé"];
    const items = buildItems(sectors.map((sector, i) => ({ symbol: `S${i}`, name: "x", sector })), {}, {});
    expect(items.map((item) => item.symbol)).toEqual(["S1", "S3", "S5", "S7", "S2", "S4", "S6", "S0"]);
    // Deux places vides séparent deux familles.
    const step = items[1].angle - items[0].angle;
    expect(items[4].angle - items[3].angle).toBeCloseTo(3 * step);
  });

  it("keeps the real pattern confidence and decision, and nothing where there is none", () => {
    const [first, second] = buildItems(securities, patterns, decisions);
    expect(first).toMatchObject({ confidence: 80, decision: "Achat" });
    expect(second).toMatchObject({ confidence: null, decision: null });
  });

  it("lengthens a spike with the pattern confidence", () => {
    const [withPattern, without] = filaments();
    expect(radius(withPattern.tip)).toBeGreaterThan(radius(without.tip));
    expect(radius(withPattern.tip)).toBeLessThanOrEqual(MAX_RADIUS);
  });

  it("keeps every spike inside the frame whatever the rotation", () => {
    const all = buildFilaments(buildItems(securities, { "AAA.PA": { confidence: 100 } }, {}));
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

  it("lists the latest decisions first, only for tracked securities", () => {
    const map = {
      "AAA.PA": { symbol: "AAA.PA", created_at: "2026-11-01T10:00:00" },
      "BBB.PA": { symbol: "BBB.PA", created_at: "2026-11-20T10:00:00" },
      "ZZZ.PA": { symbol: "ZZZ.PA", created_at: "2026-11-25T10:00:00" },
    };
    const symbols = (cards) => cards.map((card) => card.symbol);
    expect(symbols(buildCards(filaments(), map))).toEqual(["BBB.PA", "AAA.PA"]);
    // Tout tient dans le fil : il ne défile pas.
    expect(symbols(buildCards(filaments(), map, 6, 3))).toEqual(["BBB.PA", "AAA.PA"]);
  });

  it("scrolls in a loop, one card entering at the top at each step", () => {
    const map = Object.fromEntries(
      securities.map(({ symbol }, i) => [symbol, { symbol, created_at: `2026-11-0${9 - i}T10:00:00` }])
    );
    const at = (step) => buildCards(filaments(), map, 2, step).map((card) => card.symbol[0]).join("");
    expect([0, 1, 2, 3].map(at)).toEqual(["AB", "CA", "BC", "AB"]);
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
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  // Douze valeurs avec une décision, de la plus récente (V0) à la plus ancienne.
  const many = Array.from({ length: 12 }, (_, i) => ({ symbol: `V${i}.PA`, name: `Valeur ${i}`, sector: "Santé" }));
  const feedProps = {
    securities: many,
    patternsBySymbol: {},
    decisionsMap: Object.fromEntries(
      many.map(({ symbol }, i) => [symbol, { symbol, decision_type: "Achat", created_at: `2026-11-${30 - i}T10:00:00` }])
    ),
    selectedSymbol: "V0.PA",
    onSelect: () => {},
  };
  // Sélecteurs directs : les requêtes par rôle, répétées, sont très lentes dans jsdom.
  const feedGroup = () => document.querySelector('[role="group"][aria-label="Dernières décisions"]');
  const feed = () => [...feedGroup().querySelectorAll("button strong")].map((symbol) => symbol.textContent);
  const symbolsOf = (...ranks) => ranks.map((rank) => `V${rank}.PA`);
  const wait = (ms) => act(() => vi.advanceTimersByTime(ms));
  // Seul le minuteur du fil est simulé, et le tore n'est pas dessiné : sous
  // jsdom, le dessin rendrait ces tests très lents.
  const fakeFeedTimer = () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    HTMLCanvasElement.prototype.getContext.mockReturnValue(null);
  };

  it("scrolls the decisions by itself, until paused", () => {
    fakeFeedTimer();
    for (const width of [900, 360]) {
      mockContainerWidth(width);
      const { unmount } = render(<UniversTorus {...feedProps} />);
      expect(feed()).toEqual(symbolsOf(0, 1, 2, 3, 4, 5, 6, 7, 8, 9));
      wait(3000);
      expect(feed()).toEqual(symbolsOf(11, 0, 1, 2, 3, 4, 5, 6, 7, 8));
      fireEvent.click(screen.getByText("Mettre en pause"));
      wait(9000);
      expect(feed()[0]).toBe("V11.PA");
      fireEvent.click(screen.getByText("Reprendre l'animation"));
      wait(3000);
      expect(feed()[0]).toBe("V10.PA");
      unmount();
    }
  });

  it("holds the feed while the pointer or the keyboard focus is on it", () => {
    fakeFeedTimer();
    mockContainerWidth(900);
    render(<UniversTorus {...feedProps} />);
    const group = feedGroup();
    fireEvent.pointerOver(group);
    wait(9000);
    expect(feed()[0]).toBe("V0.PA");
    fireEvent.pointerOut(group);
    wait(3000);
    expect(feed()[0]).toBe("V11.PA");
    const card = group.querySelectorAll("button")[1];
    // jsdom ne sait pas dire si le focus vient du clavier : on le lui dit.
    card.matches = () => false; // focus donné par un clic
    act(() => card.focus());
    wait(3000);
    expect(feed()[0]).toBe("V10.PA");
    act(() => card.blur());
    card.matches = () => true;
    act(() => card.focus());
    wait(9000);
    expect(feed()[0]).toBe("V10.PA");
    act(() => card.blur());
    wait(3000);
    expect(feed()[0]).toBe("V9.PA");
  });

  it("finishes sliding the cards even when the torus is off screen", () => {
    vi.useFakeTimers({
      toFake: ["setInterval", "clearInterval", "requestAnimationFrame", "cancelAnimationFrame", "performance"],
    });
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback) {
          this.callback = callback;
        }
        observe() {
          this.callback([{ isIntersecting: false }]);
        }
        disconnect() {}
      }
    );
    mockContainerWidth(360);
    render(<UniversTorus {...feedProps} />);
    wait(3000);
    expect(feedGroup().style.transform).not.toBe("");
    wait(600);
    expect(feedGroup().style.transform).toBe("");
    expect(feedGroup().querySelector("button").style.opacity).toBe("");
  });

  it("does not stay held when the feed moves under the torus", () => {
    fakeFeedTimer();
    let resize;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback) {
          resize = callback;
        }
        observe() {}
        disconnect() {}
      }
    );
    const width = mockContainerWidth(900);
    render(<UniversTorus {...feedProps} />);
    fireEvent.pointerOver(feedGroup());
    width.mockReturnValue(360);
    act(() => resize());
    wait(3000);
    expect(feed()[0]).toBe("V11.PA");
  });

  it("stays still when reduced motion is requested", () => {
    fakeFeedTimer();
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    render(<UniversTorus {...feedProps} />);
    wait(9000);
    expect(feed()[0]).toBe("V0.PA");
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
    expect(screen.getByRole("button", { name: "Reprendre l'animation" })).toBeInTheDocument();
  });

  it("does not start rotating when reduced motion is requested", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    render(<UniversTorus {...props} onSelect={() => {}} />);
    expect(screen.getByRole("button", { name: "Reprendre l'animation" })).toBeInTheDocument();
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
