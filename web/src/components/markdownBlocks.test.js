import { describe, expect, it } from "vitest";
import { parseBlocks, parseInline } from "./markdownBlocks";

describe("parseBlocks", () => {
  it("splits headings, bullet and numbered lists, and paragraphs", () => {
    const md = "## Synthèse\n\n- un\n- deux\n\nTexte sur\ndeux lignes.\n\n1. premier\n2. second\n### Sous-titre";
    expect(parseBlocks(md)).toEqual([
      { type: "h2", text: "Synthèse" },
      { type: "ul", items: ["un", "deux"] },
      { type: "p", text: "Texte sur deux lignes." },
      { type: "ol", items: ["premier", "second"] },
      { type: "h3", text: "Sous-titre" },
    ]);
  });

  it("handles empty input", () => {
    expect(parseBlocks("")).toEqual([]);
    expect(parseBlocks(null)).toEqual([]);
  });
});

describe("parseInline", () => {
  it("extracts bold text and source references, keeps the rest as text", () => {
    expect(parseInline("L'inflation **accélère** à 3,1 % [4].")).toEqual([
      { type: "text", text: "L'inflation " },
      { type: "bold", text: "accélère" },
      { type: "text", text: " à 3,1 % " },
      { type: "ref", n: 4 },
      { type: "text", text: "." },
    ]);
  });

  it("never interprets HTML", () => {
    expect(parseInline("<img src=x onerror=alert(1)>")).toEqual([{ type: "text", text: "<img src=x onerror=alert(1)>" }]);
  });
});
