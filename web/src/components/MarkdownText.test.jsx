import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MarkdownText from "./MarkdownText";

const MD = "## Synthèse\n\n- **OAT** à 4,79 % [1].\n- Bund en baisse.\n\nLa dette atteint **119 %** du PIB [3].";

describe("MarkdownText audio", () => {
  let spoken;
  beforeEach(() => {
    spoken = [];
    window.SpeechSynthesisUtterance = function (text) {
      this.text = text;
    };
    window.speechSynthesis = {
      speak: vi.fn((u) => spoken.push(u.text)),
      cancel: vi.fn(),
      getVoices: () => [],
    };
  });
  afterEach(() => {
    delete window.speechSynthesis;
    delete window.SpeechSynthesisUtterance;
  });

  it("adds one listen button per paragraph and list item, not per heading", () => {
    render(<MarkdownText markdown={MD} sourceNumbers={new Set([1, 3])} />);
    expect(screen.getAllByRole("button", { name: "Écouter ce paragraphe" })).toHaveLength(3);
  });

  it("reads only that paragraph, without references, and toggles to stop", () => {
    render(<MarkdownText markdown={MD} sourceNumbers={new Set([1, 3])} />);
    const buttons = screen.getAllByRole("button", { name: "Écouter ce paragraphe" });
    fireEvent.click(buttons[2]);
    expect(spoken).toEqual(["La dette atteint 119 % du P I B."]);
    const stop = screen.getByRole("button", { name: "Arrêter la lecture" });
    expect(stop).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(stop);
    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    expect(screen.getAllByRole("button", { name: "Écouter ce paragraphe" })).toHaveLength(3);
  });

  it("shows no button when the browser has no speech synthesis", () => {
    delete window.speechSynthesis;
    render(<MarkdownText markdown={MD} />);
    expect(screen.queryByRole("button", { name: "Écouter ce paragraphe" })).toBeNull();
  });
});
