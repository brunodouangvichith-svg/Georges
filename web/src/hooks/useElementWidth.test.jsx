import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { mockContainerWidth } from "../test/containerWidth";
import { useElementWidth } from "./useElementWidth";

function Probe() {
  const [ref, width] = useElementWidth();
  return <div ref={ref}>{width ?? "inconnue"}</div>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("sans mise en page ni ResizeObserver, la largeur reste inconnue", () => {
  vi.stubGlobal("ResizeObserver", undefined);
  render(<Probe />);
  expect(screen.getByText("inconnue")).toBeInTheDocument();
});

test("suit les redimensionnements et se débranche au démontage", () => {
  let resize;
  const disconnect = vi.fn();
  vi.stubGlobal(
    "ResizeObserver",
    class {
      constructor(callback) {
        resize = callback;
      }
      observe() {}
      disconnect = disconnect;
    }
  );
  const clientWidth = mockContainerWidth(290);
  const { unmount } = render(<Probe />);
  expect(screen.getByText("290")).toBeInTheDocument();

  clientWidth.mockReturnValue(702);
  act(() => resize());
  expect(screen.getByText("702")).toBeInTheDocument();

  // Un élément masqué (largeur nulle) ne remplace pas la dernière mesure.
  clientWidth.mockReturnValue(0);
  act(() => resize());
  expect(screen.getByText("702")).toBeInTheDocument();

  unmount();
  expect(disconnect).toHaveBeenCalled();
});
