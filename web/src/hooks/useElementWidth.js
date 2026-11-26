import { useLayoutEffect, useState } from "react";

// Largeur réelle (px, arrondie à l'entier inférieur) de l'élément auquel on
// pose la `ref` renvoyée, suivie par ResizeObserver. `null` tant qu'elle est
// inconnue (élément absent ou masqué, jsdom) : l'appelant garde alors sa
// largeur par défaut. La `ref` est une fonction : elle suit aussi un élément
// monté après coup.
export function useElementWidth() {
  const [element, setElement] = useState(null);
  const [width, setWidth] = useState(null);

  useLayoutEffect(() => {
    if (!element) return;
    const measure = () => {
      const next = Math.floor(element.clientWidth);
      if (next > 0) setWidth(next);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);

  return [setElement, width];
}
