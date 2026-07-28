import { useRef, useState } from "react";

// Lecture à voix haute (Web Speech API, sortie) — miroir de useVoiceCapture.js
// (saisie) mais dans l'autre sens : window.speechSynthesis +
// SpeechSynthesisUtterance, entièrement locale au navigateur, aucune
// dépendance ni intégration backend. Contrairement au micro, l'absence de
// support (navigateur, ou jsdom en test) est traitée en silence — c'est un
// agrément de confort, pas un flux bloquant, donc pas de message d'erreur.
// Marqueurs Markdown que George écrit (titres "#", emphase "*", listes "-")
// mais ne doit pas prononcer tels quels ("dièse", "étoile", "tiret").
const SPEECH_STRIP_PATTERN = /[#*-]/g;

function sanitizeForSpeech(text) {
  return text.replace(SPEECH_STRIP_PATTERN, " ").replace(/\s+/g, " ").trim();
}

export function useSpeechOutput() {
  const [speaking, setSpeaking] = useState(false);
  const utteranceRef = useRef(null);

  function speak(text) {
    if (!window.speechSynthesis || !text) return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(sanitizeForSpeech(text));
    utterance.lang = "fr-FR";
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    utteranceRef.current = utterance;

    window.speechSynthesis.speak(utterance);
  }

  function stop() {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  return { speaking, speak, stop };
}
