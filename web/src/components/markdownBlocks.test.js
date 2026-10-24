import { describe, expect, it } from "vitest";
import { parseBlocks, parseInline, speechChunks, speechText } from "./markdownBlocks";

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

describe("speechText", () => {
  it("drops bold markers and source references and spells out abbreviations", () => {
    expect(speechText("L'OAT monte de **27,8 pb** [2][3] ; dette à **3 595,5 Md€** au T2.")).toBe(
      "L'O A T monte de 27,8 points de base; dette à 3 595,5 milliards d'euros au trimestre 2.",
    );
    expect(speechText("pente US 10 ans - 2 ans")).toBe("pente américain 10 ans moins 2 ans");
  });
});

describe("speechChunks", () => {
  it("groups sentences into chunks no longer than the limit", () => {
    const chunks = speechChunks("Une. Deux phrases ici. Trois et la fin !", 20);
    expect(chunks).toEqual(["Une.", "Deux phrases ici.", "Trois et la fin !"]);
    expect(speechChunks("Courte. Aussi.", 100)).toEqual(["Courte. Aussi."]);
  });
});
