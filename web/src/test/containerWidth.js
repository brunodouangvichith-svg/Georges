import { vi } from "vitest";

// jsdom ne met rien en page (clientWidth vaut toujours 0) : donne à tous les
// éléments la largeur voulue. À annuler avec `vi.restoreAllMocks()`.
export function mockContainerWidth(width) {
  return vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(width);
}
