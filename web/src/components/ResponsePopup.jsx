import { useEffect } from "react";
import { useSpeechOutput } from "../hooks/useSpeechOutput";

// Popup centré partagé par toutes les réponses de George (chat, explication
// de décision, commande vocale) — extrait de Univers.jsx pour être réutilisé
// par Paniers.jsx sans dupliquer le rendu.
export default function ResponsePopup({ popup, onClose, onStopListening }) {
  const { speaking, speak, stop } = useSpeechOutput();

  // George lit la réponse à voix haute dès qu'elle est disponible. Se
  // déclenche uniquement sur status "done" (pas "loading"/"error"/"prompt"/
  // "listening") ; le cleanup coupe la lecture si le popup se ferme, change
  // de contenu, ou si le composant est démonté.
  useEffect(() => {
    if (popup?.status === "done" && popup.text) {
      speak(popup.text);
    } else {
      stop();
    }
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [popup?.status, popup?.text]);

  if (!popup) return null;

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 px-6"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onClose}
    >
      <div
        className="max-w-lg w-full rounded-xl p-5 border"
        style={{ background: "var(--panel)", borderColor: "var(--hairline)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="display font-semibold text-[14px]" style={{ color: "var(--accent)" }}>
            {popup.title}
          </div>
          <div className="flex items-center gap-2">
            {popup.status === "done" && popup.text && (
              <button
                onClick={() => (speaking ? stop() : speak(popup.text))}
                style={{ color: "var(--text-dim)" }}
                title={speaking ? "Arrêter la lecture" : "Relire à voix haute"}
              >
                {speaking ? "🔊" : "🔈"}
              </button>
            )}
            <button onClick={onClose} style={{ color: "var(--text-dim)" }}>
              ✕
            </button>
          </div>
        </div>
        {popup.status === "listening" ? (
          <div className="flex flex-col items-center gap-4 py-4">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center text-[26px] gd-mic-pulse"
              style={{ background: "var(--accent-dim)", color: "var(--accent)" }}
            >
              🎙
            </div>
            <div className="text-[12px]" style={{ color: "var(--text-dim)" }}>
              Je vous écoute… (s'arrête seul au silence)
            </div>
            <div className="text-[14px] text-center min-h-[20px]">{popup.text}</div>
            <button
              className="text-[11.5px] px-3 py-1.5 rounded-full border"
              style={{ borderColor: "var(--hairline)", color: "var(--text-dim)" }}
              onClick={onStopListening}
            >
              Arrêter l'écoute
            </button>
          </div>
        ) : (
          <>
            <div
              className="text-[13px] leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto"
              style={{ color: popup.status === "error" ? "var(--negative)" : "var(--text)" }}
            >
              {popup.status === "loading" ? popup.loadingText ?? "George réfléchit…" : popup.text}
            </div>
            {popup.status === "prompt" && popup.actionLabel && (
              <button
                className="mt-3 w-full py-2.5 rounded-lg font-semibold text-[13px]"
                style={{ background: "var(--accent)", color: "#fff" }}
                onClick={popup.onAction}
              >
                {popup.actionLabel}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
