import { useParagraphSpeech } from "../hooks/useParagraphSpeech";
import { parseBlocks, parseInline, speechText } from "./markdownBlocks";

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

// Bouton 🔈/⏹ devant un paragraphe : lit ce paragraphe seul, ou l'arrête.
function ListenButton({ id, text, speech }) {
  if (!speech.supported) return null;
  const active = speech.speakingId === id;
  return (
    <button
      type="button"
      onClick={() => (active ? speech.stop() : speech.speak(id, speechText(text)))}
      aria-pressed={active}
      aria-label={active ? "Arrêter la lecture" : "Écouter ce paragraphe"}
      title={active ? "Arrêter la lecture" : "Écouter ce paragraphe"}
      className="shrink-0 w-6 h-6 -ml-1 mt-px rounded-full text-[12px] leading-none flex items-center justify-center border"
      style={{
        borderColor: active ? "var(--accent)" : "var(--hairline)",
        color: active ? "var(--accent)" : "var(--text-dim)",
        background: active ? "var(--panel-alt)" : "transparent",
      }}
    >
      {active ? "⏹" : "🔈"}
    </button>
  );
}

export default function MarkdownText({ markdown, sourceNumbers }) {
  const blocks = parseBlocks(markdown);
  const speech = useParagraphSpeech();
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
                  <span className="inline-flex gap-2 align-top w-full">
                    <ListenButton id={`${i}-${j}`} text={item} speech={speech} />
                    <span className="min-w-0">
                      <Inline text={item} sourceNumbers={sourceNumbers} />
                    </span>
                  </span>
                </li>
              ))}
            </Tag>
          );
        }
        return (
          <div key={i} className="flex gap-2">
            <ListenButton id={String(i)} text={block.text} speech={speech} />
            <p className="m-0 min-w-0">
              <Inline text={block.text} sourceNumbers={sourceNumbers} />
            </p>
          </div>
        );
      })}
    </div>
  );
}
