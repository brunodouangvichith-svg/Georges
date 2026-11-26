import { useState, useSyncExternalStore } from "react";
import { getInstallPrompt, isIos, isStandalone, promptInstall, subscribeInstallPrompt } from "../lib/install";

const DISMISSED_KEY = "george-install-dismissed";

function wasDismissed() {
  try {
    return localStorage.getItem(DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

// Barre « Installer George » sous l'en-tête, sur téléphone seulement (classe
// .gd-install) et jamais dans l'application déjà installée.
export default function InstallBar() {
  const prompt = useSyncExternalStore(subscribeInstallPrompt, getInstallPrompt);
  const [hidden, setHidden] = useState(() => isStandalone() || wasDismissed());
  const [help, setHelp] = useState(false);

  if (hidden) return null;

  function dismiss() {
    setHidden(true);
    try {
      localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // Navigation privée : la barre reviendra à la prochaine visite.
    }
  }

  return (
    <div className="gd-install">
      <div className="flex items-center gap-2">
        <button
          className="gd-btn flex-1"
          aria-expanded={prompt ? undefined : help}
          onClick={() => (prompt ? promptInstall() : setHelp((v) => !v))}
        >
          <span aria-hidden="true">📲 </span>Installer George
        </button>
        <button className="gd-btn gd-icon-btn" aria-label="Masquer la barre d'installation" onClick={dismiss}>
          ✕
        </button>
      </div>
      {help && !prompt && (
        <p className="m-0 mt-2 text-[12.5px]" style={{ color: "var(--text-dim)" }}>
          {isIos()
            ? "Dans Safari : bouton Partager, puis « Sur l'écran d'accueil »."
            : "Menu ⋮ du navigateur, puis « Installer l'application » ou « Ajouter à l'écran d'accueil »."}
        </p>
      )}
    </div>
  );
}
