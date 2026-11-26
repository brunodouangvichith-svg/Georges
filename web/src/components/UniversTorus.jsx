import { useEffect, useMemo, useRef, useState } from "react";
import { decisionColor } from "../data";
import { useElementWidth } from "../hooks/useElementWidth";
import { buildFilaments, buildStrands, makeProjector, nearestFilament } from "./torusLayout";
import { buildRadar } from "./universRadarLayout";

// Tore 3D de l'univers (écran Univers, bascule « Radar / Tore 3D »).
//
// - Chaque valeur suivie = une boucle autour du tube et une antenne sur le bord
//   extérieur, dans le même ordre par secteur que le radar.
// - Longueur de l'antenne = confiance de la dernière figure détectée ; couleur
//   = décision en cours (bleu sans décision). La valeur sélectionnée est
//   surlignée en blanc.
// - Les autres fils sont décoratifs et ne représentent aucune donnée.
//
// Glisser fait tourner le tore, un clic près d'une antenne sélectionne la
// valeur (raccourci : le menu « Choisir une valeur » reste le chemin
// clavier/lecteur d'écran). La rotation automatique se met en pause avec le
// bouton, et ne démarre pas si le système demande moins d'animations.
//
// Dessiné sur un <canvas> 2D (perspective calculée à la main) : quelques
// milliers de segments par image, sans bibliothèque 3D.

const STRANDS = buildStrands();
const SPIN = 0.12; // radians par seconde
const DRAG = 0.008; // radians par pixel glissé
const CLICK_SLOP = 5; // au-delà, le geste est un glisser, pas un clic
const MAX_TILT = 1.35;
const CARD_WIDTH = 150; // carte de la valeur sélectionnée, en haut à droite
const CARD_HEIGHT = 44;

function reducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

// Le canvas ne comprend pas var(--x) : on lit la valeur de la variable.
function resolveColor(element, color) {
  const name = /^var\((--[\w-]+)\)$/.exec(color)?.[1];
  if (!name) return color;
  return getComputedStyle(element).getPropertyValue(name).trim() || "#8b96b8";
}

function stroke(ctx, project, points) {
  points.forEach((point, i) => {
    const { x, y } = project(point);
    if (i) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  });
}

function draw(canvas, ctx, { filaments, selectedSymbol, yaw, tilt, width, height }) {
  const project = makeProjector({ yaw, tilt, width, height });
  // Une seule lecture de style par couleur et par image.
  const cache = new Map();
  const color = (value) => {
    if (!cache.has(value)) cache.set(value, resolveColor(canvas, value));
    return cache.get(value);
  };
  ctx.clearRect(0, 0, width, height);
  // Les fils superposés s'additionnent : les zones denses s'illuminent.
  ctx.globalCompositeOperation = "lighter";

  ctx.lineWidth = 0.5;
  ctx.strokeStyle = color("var(--text-dim)");
  ctx.globalAlpha = 0.22;
  for (const strand of STRANDS) {
    ctx.beginPath();
    stroke(ctx, project, strand);
    ctx.stroke();
  }

  let selected = null;
  for (const filament of filaments) {
    if (filament.symbol === selectedSymbol) {
      selected = filament;
      continue;
    }
    const tint = color(filament.decision ? decisionColor(filament.decision) : "var(--accent)");
    const strength = (filament.confidence ?? 0) / 100;
    const base = project(filament.base);
    const tip = project(filament.tip);
    // Les antennes de l'arrière sont atténuées pour donner le relief.
    const near = tip.depth > 0 ? 1 : 0.55;
    ctx.strokeStyle = tint;
    ctx.fillStyle = tint;
    ctx.lineWidth = 0.7;
    ctx.globalAlpha = 0.1 + strength * 0.3;
    ctx.beginPath();
    stroke(ctx, project, filament.loop);
    ctx.stroke();
    ctx.lineWidth = strength >= 0.75 ? 1.8 : 1;
    ctx.globalAlpha = (filament.confidence == null ? 0.4 : 0.95) * near;
    ctx.beginPath();
    ctx.moveTo(base.x, base.y);
    ctx.lineTo(tip.x, tip.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(tip.x, tip.y, filament.confidence == null ? 1 : 2.2, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  if (!selected) return;
  const text = color("var(--text)");
  const base = project(selected.base);
  const tip = project(selected.tip);
  ctx.strokeStyle = text;
  ctx.fillStyle = text;
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  stroke(ctx, project, selected.loop);
  ctx.stroke();
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(base.x, base.y);
  ctx.lineTo(tip.x, tip.y);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(tip.x, tip.y, 4.5, 0, Math.PI * 2);
  ctx.fill();

  // Le lien : une courbe de l'antenne à la carte, qui suit la rotation.
  const endX = width - CARD_WIDTH;
  const endY = CARD_HEIGHT / 2;
  ctx.strokeStyle = color(selected.decision ? decisionColor(selected.decision) : "var(--accent)");
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(tip.x, tip.y);
  ctx.bezierCurveTo(tip.x, (tip.y + endY) / 2, endX - 80, endY, endX, endY);
  ctx.stroke();
}

export default function UniversTorus({ securities, patternsBySymbol, decisionsMap, selectedSymbol, onSelect }) {
  const filaments = useMemo(
    () => buildFilaments(buildRadar(securities, patternsBySymbol, decisionsMap).items),
    [securities, patternsBySymbol, decisionsMap]
  );
  const [boxRef, boxWidth] = useElementWidth();
  const width = boxWidth ?? 640;
  const height = Math.round(Math.min(width, 640));
  const canvasRef = useRef(null);
  const angles = useRef({ yaw: -0.55, tilt: 0.42 });
  const drag = useRef(null);
  const redrawRef = useRef(() => {});
  const [spinning, setSpinning] = useState(() => !reducedMotion());

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const redraw = () => draw(canvas, ctx, { filaments, selectedSymbol, width, height, ...angles.current });
    redrawRef.current = redraw;
    redraw();
    if (!spinning) return;
    let frame;
    let previous = null;
    const tick = (now) => {
      // Écart borné : au retour sur l'onglet, le tore ne saute pas.
      if (previous != null && !drag.current) angles.current.yaw += (Math.min(now - previous, 100) / 1000) * SPIN;
      previous = now;
      if (visible) redraw();
      frame = requestAnimationFrame(tick);
    };
    // Hors de l'écran (page défilée), on ne dessine plus.
    let visible = true;
    const observer =
      typeof IntersectionObserver === "undefined"
        ? null
        : new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
          });
    observer?.observe(canvas);
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, [filaments, selectedSymbol, width, height, spinning]);

  function onPointerDown(event) {
    // Un seul pointeur à la fois : un second doigt est ignoré.
    if (event.button > 0 || drag.current) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, travelled: 0 };
  }

  function onPointerMove(event) {
    const last = drag.current;
    if (!last || last.id !== event.pointerId) return;
    const dx = event.clientX - last.x;
    const dy = event.clientY - last.y;
    drag.current = { id: last.id, x: event.clientX, y: event.clientY, travelled: last.travelled + Math.hypot(dx, dy) };
    angles.current.yaw += dx * DRAG;
    angles.current.tilt = Math.max(-MAX_TILT, Math.min(MAX_TILT, angles.current.tilt - dy * DRAG));
    redrawRef.current();
  }

  function onPointerUp(event) {
    const last = drag.current;
    if (!last || last.id !== event.pointerId) return;
    drag.current = null;
    if (last.travelled > CLICK_SLOP) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const hit = nearestFilament(
      filaments,
      makeProjector({ width, height, ...angles.current }),
      event.clientX - rect.left,
      event.clientY - rect.top
    );
    if (hit) onSelect(hit.symbol);
  }

  const withPattern = filaments.filter((f) => f.confidence != null).length;
  const selected = filaments.find((f) => f.symbol === selectedSymbol) ?? null;

  return (
    <div ref={boxRef} className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width, maxWidth: "100%" }}>
      {selected && (
        <div
          className="mono absolute right-0 top-0 flex flex-col justify-center rounded-lg border px-2 text-[11.5px]"
          style={{
            width: CARD_WIDTH,
            height: CARD_HEIGHT,
            background: "var(--panel)",
            borderColor: selected.decision ? decisionColor(selected.decision) : "var(--accent)",
            pointerEvents: "none",
          }}
        >
          <strong className="truncate">{selected.symbol}</strong>
          <span className="truncate">
            {selected.confidence == null ? "sans figure" : `${Math.round(selected.confidence)} %`}
            {selected.decision ? ` · ${selected.decision}` : ""}
          </span>
        </div>
      )}
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={
          `Tore 3D de l'univers : ${filaments.length} valeurs, ${withPattern} avec une figure détectée. ` +
          "La longueur des antennes suit la confiance de la figure."
        }
        style={{ display: "block", width, height, maxWidth: "100%", touchAction: "pan-y pinch-zoom", cursor: "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={(event) => {
          if (drag.current?.id === event.pointerId) drag.current = null;
        }}
      />
      </div>
      <p className="m-0 text-center text-[11px]" style={{ color: "var(--text-dim)" }}>
        Antenne = confiance de la figure · couleur = décision (vert achat ou renfort, orange surveiller, rouge alléger,
        bleu aucune) · les autres fils sont décoratifs
      </p>
      <button type="button" className="gd-btn" onClick={() => setSpinning((on) => !on)}>
        {spinning ? "Mettre en pause" : "Faire tourner"}
      </button>
    </div>
  );
}
