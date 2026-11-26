import { useEffect, useRef } from "react";

// Le bouton (ou geste) retour du téléphone ferme la fenêtre ouverte au lieu de
// quitter l'application : l'ouverture ajoute une entrée d'historique, retirée
// à la fermeture quel qu'en soit le moyen.
export function useBackToClose(open, onClose) {
  const onCloseRef = useRef(onClose);
  const openRef = useRef(false);

  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    openRef.current = true;
    if (!window.history.state?.popup) {
      window.history.pushState({ ...window.history.state, popup: true }, "");
    }
    const onPop = () => onCloseRef.current();
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      openRef.current = false;
      // Différé : en mode strict React rejoue l'effet aussitôt, et la fenêtre
      // est alors toujours ouverte.
      setTimeout(() => {
        if (!openRef.current && window.history.state?.popup) window.history.back();
      }, 0);
    };
  }, [open]);
}
