import { useEffect, useRef, useState } from "react";

export const MAX_ZOOM = 5;

const FULL = { k: 1, x: 0, y: 0 };

const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

// Centre des (au plus) deux premiers doigts, et leur écartement (0 si un seul).
function fingers(touches) {
  const [a, b] = touches;
  if (!b) return { x: a.clientX, y: a.clientY, dist: 0 };
  return {
    x: (a.clientX + b.clientX) / 2,
    y: (a.clientY + b.clientY) / 2,
    dist: Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY),
  };
}

// Zoom au pincement d'un SVG de `width` × `height` unités : deux doigts
// agrandissent la figure (le point entre les doigts reste sous les doigts),
// un doigt la déplace une fois agrandie. En vue entière, un doigt continue de
// faire défiler la page. Le SVG doit garder les proportions de sa viewBox.
export function usePinchZoom(width, height) {
  const ref = useRef(null);
  const [view, setView] = useState(FULL);
  // Vue courante, lisible par les écouteurs sans attendre le rendu suivant.
  const viewRef = useRef(FULL);
  // Point de départ du geste : repris à chaque doigt posé ou levé.
  const startRef = useRef(null);

  function apply(next) {
    viewRef.current = next;
    setView(next);
  }

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function rebase(event) {
      startRef.current = event.touches.length ? { ...fingers(event.touches), view: viewRef.current } : null;
    }

    function move(event) {
      const start = startRef.current;
      if (!start || (event.touches.length < 2 && viewRef.current.k === 1)) return;
      if (!event.cancelable) return; // la page défile déjà : ne pas zoomer en même temps
      event.preventDefault(); // la page ne doit ni défiler ni zoomer à la place
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const now = fingers(event.touches);
      const from = start.view;
      let k = start.dist && now.dist ? clamp((from.k * now.dist) / start.dist, 1, MAX_ZOOM) : from.k;
      if (k < 1.02) k = 1; // retour franc à la vue entière
      // Point de la figure qui se trouvait sous les doigts au départ.
      const px = from.x + ((start.x - rect.left) / rect.width) * (width / from.k);
      const py = from.y + ((start.y - rect.top) / rect.height) * (height / from.k);
      apply({
        k,
        x: clamp(px - ((now.x - rect.left) / rect.width) * (width / k), 0, width - width / k),
        y: clamp(py - ((now.y - rect.top) / rect.height) * (height / k), 0, height - height / k),
      });
    }

    // `passive: false` : React pose ses écouteurs en passif, où
    // preventDefault() est ignoré.
    el.addEventListener("touchstart", rebase, { passive: true });
    el.addEventListener("touchmove", move, { passive: false });
    el.addEventListener("touchend", rebase);
    el.addEventListener("touchcancel", rebase);
    return () => {
      el.removeEventListener("touchstart", rebase);
      el.removeEventListener("touchmove", move);
      el.removeEventListener("touchend", rebase);
      el.removeEventListener("touchcancel", rebase);
    };
  }, [width, height]);

  const zoomed = view.k > 1;
  return {
    ref,
    view,
    zoomed,
    viewBox: `${view.x} ${view.y} ${width / view.k} ${height / view.k}`,
    touchAction: zoomed ? "none" : "pan-y",
    reset: () => apply(FULL),
  };
}
