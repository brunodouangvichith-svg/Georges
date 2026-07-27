import { useRef } from "react";

// La reconnaissance vocale de Chrome/Edge n'est pas locale : l'audio est
// envoyé aux serveurs de Google pour être transcrit, d'où un code "network"
// (pas un vrai problème de connexion Internet en général) si un bloqueur de
// pub/VPN/pare-feu d'entreprise empêche cette requête sortante.
const VOICE_ERROR_MESSAGES = {
  network:
    "Le micro n'a pas pu joindre le service de reconnaissance vocale de Google (utilisé par Chrome/Edge). Vérifiez un éventuel bloqueur de pub/extension de confidentialité, VPN, ou pare-feu d'entreprise qui bloquerait ce trafic sortant, puis réessayez.",
  "not-allowed": "Accès au micro refusé — autorisez-le dans les paramètres du navigateur pour ce site puis réessayez.",
  "no-speech":
    "Aucune parole détectée avant la fin de l'écoute — réessayez en parlant un peu plus fort ou plus vite après avoir cliqué.",
  "audio-capture": "Aucun micro détecté sur cet appareil.",
};

// Capture vocale générique (Web Speech API) — extrait de Univers.jsx pour
// être réutilisé (ex. Mon Portefeuille) sans dupliquer la configuration de
// `SpeechRecognition` ni les messages d'erreur. Le composant appelant
// décide de ce qu'il fait du texte final (`onFinal`) — poser une question à
// George, répartir un budget, etc.
export function useVoiceCapture({ onListening, onInterim, onError, onFinal }) {
  const recognitionRef = useRef(null);
  const transcriptRef = useRef("");

  function start() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      onError?.("La reconnaissance vocale n'est pas prise en charge par ce navigateur — essayez Chrome ou Edge.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "fr-FR";
    recognition.continuous = false; // s'arrête d'elle-même dès qu'un silence est détecté
    recognition.interimResults = true;
    recognitionRef.current = recognition;
    transcriptRef.current = "";

    onListening?.();

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
      transcriptRef.current = transcript;
      onInterim?.(transcript);
    };

    recognition.onerror = (event) => {
      recognitionRef.current = null;
      onError?.(VOICE_ERROR_MESSAGES[event.error] ?? `Erreur micro : ${event.error}`);
    };

    // Se déclenche automatiquement dès que la reconnaissance détecte un
    // silence (recognition.continuous = false) — pas besoin de minuterie
    // manuelle pour "terminer sur silence".
    recognition.onend = () => {
      recognitionRef.current = null;
      onFinal?.(transcriptRef.current.trim());
    };

    recognition.start();
  }

  function stop() {
    recognitionRef.current?.stop();
  }

  function abort() {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
  }

  return { start, stop, abort };
}
