import { parseBlocks, parseInline } from "./markdownBlocks";

// Rendu du commentaire Markdown du rapport stratégique. Les renvois [n]
// deviennent des liens vers la source n de la liste des sources (ancre
// `source-n`) quand elle existe, sinon restent du texte.
function Inline({ text, sourceNumbers }) {
  return parseInline(text).map((seg, i) => {
    if (seg.type === "bold") return <strong key={i}>{seg.text}</strong>;
    if (seg.type === "ref") {
      return sourceNumbers?.has(seg.n) ? (
        <a key={i} href={`#source-${seg.n}`} className="mono text-[11px] align-super" style={{ color: "var(--accent)" }}>
          [{seg.n}]
        </a>
      ) : (
        <span key={i}>[{seg.n}]</span>
      );
    }
    return <span key={i}>{seg.text}</span>;
  });
}

export default function MarkdownText({ markdown, sourceNumbers }) {
  const blocks = parseBlocks(markdown);
  return (
    <div className="flex flex-col gap-2.5 text-[13.5px] leading-relaxed">
      {blocks.map((block, i) => {
        if (block.type === "h2")
          return (
            <h3 key={i} className="m-0 mt-3 first:mt-0 text-[15px] font-semibold" style={{ color: "var(--text)" }}>
              <Inline text={block.text} sourceNumbers={sourceNumbers} />
            </h3>
          );
        if (block.type === "h3")
          return (
            <h4 key={i} className="m-0 mt-1 text-[13.5px] font-semibold" style={{ color: "var(--text)" }}>
              <Inline text={block.text} sourceNumbers={sourceNumbers} />
            </h4>
          );
        if (block.type === "ul" || block.type === "ol") {
          const Tag = block.type;
          return (
            <Tag key={i} className={`m-0 pl-5 flex flex-col gap-1 ${block.type === "ul" ? "list-disc" : "list-decimal"}`}>
              {block.items.map((item, j) => (
                <li key={j}>
                  <Inline text={item} sourceNumbers={sourceNumbers} />
                </li>
              ))}
            </Tag>
          );
        }
        return (
          <p key={i} className="m-0">
            <Inline text={block.text} sourceNumbers={sourceNumbers} />
          </p>
        );
      })}
    </div>
  );
}
