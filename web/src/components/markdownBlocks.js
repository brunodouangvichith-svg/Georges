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
