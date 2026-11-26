import { useCallback, useEffect, useState } from "react";

// L'onglet affiché est porté par l'adresse (?view=trading) : le retour du
// téléphone revient à l'onglet précédent, et les raccourcis de l'icône
// installée (vite.config.js) ouvrent directement le bon écran.
// `views` doit être une constante : la première est l'écran par défaut.
export function useViewHistory(views) {
  const read = useCallback(() => {
    const asked = new URLSearchParams(window.location.search).get("view");
    return views.includes(asked) ? asked : views[0];
  }, [views]);
  const [view, setViewState] = useState(read);

  useEffect(() => {
    const onPop = () => setViewState(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [read]);

  const setView = useCallback(
    (next) => {
      if (next === read()) return;
      const url = new URL(window.location.href);
      if (next === views[0]) url.searchParams.delete("view");
      else url.searchParams.set("view", next);
      window.history.pushState({}, "", url);
      setViewState(next);
    },
    [read, views],
  );

  return [view, setView];
}
