import { StrictMode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { useBackToClose } from "./useBackToClose";
import { useViewHistory } from "./useViewHistory";
import { isIos } from "../lib/install";

const VIEWS = ["univers", "trading"];
const tick = () => new Promise((resolve) => setTimeout(resolve, 20));

beforeEach(() => window.history.replaceState({}, "", "/"));

test("l'onglet suit l'adresse et le retour revient au précédent", async () => {
  const { result } = renderHook(() => useViewHistory(VIEWS));
  expect(result.current[0]).toBe("univers");
  act(() => result.current[1]("trading"));
  expect(window.location.search).toBe("?view=trading");
  act(() => window.history.back());
  await waitFor(() => expect(result.current[0]).toBe("univers"));
});

test("un raccourci ouvre l'écran demandé, un nom inconnu l'Univers", () => {
  window.history.replaceState({}, "", "/?view=trading");
  expect(renderHook(() => useViewHistory(VIEWS)).result.current[0]).toBe("trading");
  window.history.replaceState({}, "", "/?view=nimporte");
  expect(renderHook(() => useViewHistory(VIEWS)).result.current[0]).toBe("univers");
});

test("le retour ferme la fenêtre ouverte", async () => {
  const onClose = vi.fn();
  renderHook(() => useBackToClose(true, onClose), { wrapper: StrictMode });
  await act(tick);
  expect(onClose).not.toHaveBeenCalled();
  expect(window.history.state.popup).toBe(true);
  act(() => window.history.back());
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
});

test("fermer par le bouton retire l'entrée d'historique", async () => {
  const { rerender } = renderHook(({ open }) => useBackToClose(open, () => {}), {
    initialProps: { open: true },
    wrapper: StrictMode,
  });
  rerender({ open: false });
  await waitFor(() => expect(window.history.state?.popup).toBeUndefined());
});

test("reconnaît l'iPhone et l'iPad", () => {
  expect(isIos({ userAgent: "Mozilla/5.0 (iPhone)", platform: "iPhone", maxTouchPoints: 5 })).toBe(true);
  expect(isIos({ userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel", maxTouchPoints: 5 })).toBe(true);
  expect(isIos({ userAgent: "Mozilla/5.0 (Linux; Android 14)", platform: "Linux", maxTouchPoints: 5 })).toBe(false);
});
