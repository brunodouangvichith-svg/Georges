import { useEffect, useRef, useState } from "react";
import { speechChunks } from "../components/markdownBlocks";

// Lecture à voix haute d'un paragraphe à la fois (Web Speech API, locale au
// navigateur, rien côté serveur). `speakingId` dit quel paragraphe est lu ;
// relancer un autre paragraphe coupe le précédent. Sans support (vieux
// navigateur, jsdom), `supported` est faux et l'appelant masque les boutons.
export function useParagraphSpeech() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function";
  const [speakingId, setSpeakingId] = useState(null);
  const runRef = useRef(0);

  function stop() {
    runRef.current += 1;
    if (supported) window.speechSynthesis.cancel();
    setSpeakingId(null);
  }

  function speak(id, text) {
    if (!supported || !text) return;
    stop();
    const run = runRef.current;
    const chunks = speechChunks(text);
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith("fr"));
    setSpeakingId(id);
    chunks.forEach((chunk, i) => {
      const utterance = new window.SpeechSynthesisUtterance(chunk);
      utterance.lang = "fr-FR";
      if (voice) utterance.voice = voice;
      if (i === chunks.length - 1) {
        utterance.onend = () => runRef.current === run && setSpeakingId(null);
      }
      utterance.onerror = () => runRef.current === run && setSpeakingId(null);
      window.speechSynthesis.speak(utterance);
    });
  }

  // Couper la voix si on quitte l'écran en pleine lecture.
  useEffect(
    () => () => {
      window.speechSynthesis?.cancel();
    },
    [supported],
  );

  return { supported, speakingId, speak, stop };
}
