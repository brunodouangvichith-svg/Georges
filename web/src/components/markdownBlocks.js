// Découpe minimale du Markdown produit par le rapport stratégique (titres
// ##/###, puces, listes numérotées, paragraphes, **gras**, renvois [n]) en
// blocs, sans jamais passer par innerHTML : le texte vient d'un LLM, il est
// rendu comme du texte, jamais comme du HTML.

export function parseBlocks(markdown) {
  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "p", text: paragraph.join(" ") });
    paragraph = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const raw of (markdown ?? "").split("\n")) {
    const line = raw.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({ type: heading[1].length <= 2 ? "h2" : "h3", text: heading[2] });
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      flushParagraph();
      const type = bullet ? "ul" : "ol";
      if (!list || list.type !== type) {
        flushList();
        list = { type, items: [] };
      }
      list.items.push((bullet ?? numbered)[1]);
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

// Segments d'une ligne : texte, gras, renvoi à une source numérotée.
export function parseInline(text) {
  const segments = [];
  const re = /\*\*(.+?)\*\*|\[(\d{1,3})\]/g;
  let last = 0;
  let match;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) segments.push({ type: "text", text: text.slice(last, match.index) });
    if (match[1] !== undefined) segments.push({ type: "bold", text: match[1] });
    else segments.push({ type: "ref", n: Number(match[2]) });
    last = re.lastIndex;
  }
  if (last < text.length) segments.push({ type: "text", text: text.slice(last) });
  return segments;
}

// Texte à prononcer pour une ligne du rapport : sans gras ni renvois [n], et
// avec les abréviations financières dites en toutes lettres (une voix lit
// sinon "pb" lettre par lettre ou "Md€" comme "M D euro").
const SPOKEN_ABBREVIATIONS = [
  [/(\d)\s*pb\b/g, "$1 points de base"],
  [/\bMd€/g, "milliards d'euros"],
  [/\bMds?\b/g, "milliards"],
  [/(\d)\s*M€/g, "$1 millions d'euros"],
  [/\bT([1-4])\b/g, "trimestre $1"],
  [/\bOAT\b/g, "O A T"],
  [/\bPIB\b/g, "P I B"],
  [/\bUS\b/g, "américain"],
  [/\s-\s/g, " moins "],
];

export function speechText(text) {
  let out = parseInline(text ?? "")
    .filter((seg) => seg.type !== "ref")
    .map((seg) => seg.text)
    .join("");
  for (const [re, by] of SPOKEN_ABBREVIATIONS) out = out.replace(re, by);
  return out.replace(/\s+([.,;:])/g, "$1").replace(/\s+/g, " ").trim();
}

// Découpe en phrases : Chrome coupe une seule SpeechSynthesisUtterance
// longue au bout d'une quinzaine de secondes, on enchaîne donc des phrases.
export function speechChunks(text, maxLength = 220) {
  const sentences = text.split(/(?<=[.!?;])\s+/).map((s) => s.trim()).filter(Boolean);
  const chunks = [];
  for (const sentence of sentences) {
    const last = chunks.at(-1);
    if (last && last.length + sentence.length + 1 <= maxLength) chunks[chunks.length - 1] = `${last} ${sentence}`;
    else chunks.push(sentence);
  }
  return chunks;
}
