import { useEffect, useMemo, useRef, useState } from "react";
import { decisionColor } from "../data";
import { useElementWidth } from "../hooks/useElementWidth";
import { eur } from "../lib/format";
import { buildCards, buildFilaments, buildStrands, makeProjector, nearestFilament } from "./torusLayout";
import { buildRadar } from "./universRadarLayout";

// Tore 3D de l'univers (écran Univers, bascule « Radar / Tore 3D »).
//
// - Chaque valeur suivie = une boucle autour du tube et une antenne sur le bord
//   extérieur, dans le même ordre par secteur que le radar.
// - Longueur de l'antenne = confiance de la dernière figure détectée ; couleur
//   = décision en cours (bleu sans décision). La valeur sélectionnée est
//   surlignée en blanc.
// - Les autres fils sont décoratifs et ne représentent aucune donnée.
// - Les dernières décisions sont des cartes, à droite quand la place le permet,
//   chacune reliée à son antenne par une courbe ; sur écran étroit elles passent
//   sous le tore, sans courbe. Un clic sur une carte sélectionne la valeur.
//
// Le tore tourne sur son axe (celui du trou). Glisser horizontalement le fait
// tourner, verticalement incline la vue ; un clic près d'une antenne
// sélectionne la valeur. Au clavier : les cartes ou le menu « Choisir une
// valeur ». La rotation automatique se met en pause avec le bouton, et ne
// démarre pas si le système demande moins d'animations.
//
// Dessiné sur un <canvas> 2D (perspective calculée à la main) : quelques
// milliers de segments par image, sans bibliothèque 3D.

const STRANDS = buildStrands();
const SPIN = 0.18; // radians par seconde
const DRAG = 0.008; // radians par pixel glissé
const CLICK_SLOP = 5; // au-delà, le geste est un glisser, pas un clic
const MAX_TILT = 1.35;
const CARDS_FROM = 600; // largeur à partir de laquelle les cartes sont à droite
const CARD_COUNT = 6;
const CARD_HEIGHT = 58;
const CARD_STEP = CARD_HEIGHT + 8;
const LINK_GAP = 24; // espace réservé aux courbes devant les cartes

const decisionTint = (decision) => (decision ? decisionColor(decision) : "var(--accent)");

// Jour et mois seulement : la date longue ne tient pas dans une carte.
const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }) : "—";

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

function draw(canvas, ctx, { filaments, selectedSymbol, links, view, width, height, torusWidth }) {
  // Le tore occupe la partie gauche du canvas ; les courbes vont vers la droite.
  const project = makeProjector({ ...view, width: torusWidth, height });
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
    const tint = color(decisionTint(filament.decision));
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
  if (selected) drawSelected(ctx, project, selected, color("var(--text)"));

  // Les liens : une courbe par carte, de son antenne à son bord gauche.
  for (const link of links) {
    const tip = project(link.tip);
    const chosen = link.symbol === selectedSymbol;
    const tint = color(decisionTint(link.decision));
    ctx.strokeStyle = tint;
    ctx.fillStyle = tint;
    // Antenne passée derrière le tore : courbe atténuée.
    ctx.globalAlpha = (chosen ? 1 : 0.7) * (tip.depth > 0 ? 1 : 0.5);
    ctx.lineWidth = chosen ? 2.4 : 1.2;
    ctx.beginPath();
    ctx.moveTo(tip.x, tip.y);
    ctx.bezierCurveTo(tip.x + (link.x - tip.x) * 0.6, tip.y, link.x - 60, link.y, link.x, link.y);
    ctx.stroke();
    for (const [x, y] of [
      [tip.x, tip.y],
      [link.x, link.y],
    ]) {
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}

function drawSelected(ctx, project, selected, color) {
  const base = project(selected.base);
  const tip = project(selected.tip);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
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
}

function Card({ card, selected, onSelect, style }) {
  const { detail } = card;
  const tint = decisionTint(card.decision);
  return (
    <button
      type="button"
      className="gd-focus mono flex flex-col justify-center rounded-lg px-2 text-left text-[11px] cursor-pointer"
      aria-pressed={selected}
      onClick={() => onSelect(card.symbol)}
      style={{
        height: CARD_HEIGHT,
        background: selected ? "var(--panel-alt)" : "var(--panel)",
        border: `1px solid ${selected ? "var(--text)" : tint}`,
        borderLeft: `3px solid ${tint}`,
        color: "var(--text)",
        ...style,
      }}
    >
      <span className="flex justify-between gap-2">
        <strong className="truncate">{card.symbol}</strong>
        <span className="truncate">{card.decision ?? "aucune décision"}</span>
      </span>
      {detail ? (
        <>
          <span className="truncate">
            TP {eur(detail.take_profit)} · SL {eur(detail.stop_loss)}
          </span>
          <span className="truncate" style={{ color: "var(--text-dim)" }}>
            Entrée {eur(detail.entry_price)} · {shortDate(detail.created_at)}
          </span>
        </>
      ) : (
        <span className="truncate" style={{ color: "var(--text-dim)" }}>
          {card.confidence == null ? "sans figure" : `figure à ${Math.round(card.confidence)} %`}
        </span>
      )}
    </button>
  );
}

export default function UniversTorus({ securities, patternsBySymbol, decisionsMap, selectedSymbol, onSelect }) {
  const filaments = useMemo(
    () => buildFilaments(buildRadar(securities, patternsBySymbol, decisionsMap).items),
    [securities, patternsBySymbol, decisionsMap]
  );
  const cards = useMemo(
    () => buildCards(filaments, decisionsMap, selectedSymbol, CARD_COUNT),
    [filaments, decisionsMap, selectedSymbol]
  );
  const [boxRef, boxWidth] = useElementWidth();
  const width = boxWidth ?? 640;
  const aside = width >= CARDS_FROM && cards.length > 0;
  const cardWidth = aside ? Math.round(Math.min(270, width * 0.34)) : 0;
  const torusWidth = aside ? width - cardWidth - LINK_GAP : width;
  const cardsHeight = aside ? cards.length * CARD_STEP - 8 : 0;
  const height = Math.round(Math.max(Math.min(torusWidth, 640), cardsHeight));
  const cardsTop = Math.round((height - cardsHeight) / 2);
  const links = useMemo(
    () =>
      aside
        ? cards.map((card, i) => ({
            symbol: card.symbol,
            decision: card.decision,
            tip: card.tip,
            x: width - cardWidth,
            y: cardsTop + i * CARD_STEP + CARD_HEIGHT / 2,
          }))
        : [],
    [aside, cards, width, cardWidth, cardsTop]
  );
  const canvasRef = useRef(null);
  const view = useRef({ spin: 0, yaw: -0.7, tilt: 0.25 });
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
    const redraw = () =>
      draw(canvas, ctx, { filaments, selectedSymbol, links, view: view.current, width, height, torusWidth });
    redrawRef.current = redraw;
    redraw();
    if (!spinning) return;
    let frame;
    let previous = null;
    const tick = (now) => {
      // Écart borné : au retour sur l'onglet, le tore ne saute pas.
      if (previous != null && !drag.current) view.current.spin += (Math.min(now - previous, 100) / 1000) * SPIN;
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
  }, [filaments, selectedSymbol, links, width, height, torusWidth, spinning]);

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
    view.current.spin += dx * DRAG;
    view.current.tilt = Math.max(-MAX_TILT, Math.min(MAX_TILT, view.current.tilt - dy * DRAG));
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
      makeProjector({ ...view.current, width: torusWidth, height }),
      event.clientX - rect.left,
      event.clientY - rect.top
    );
    if (hit) onSelect(hit.symbol);
  }

  const withPattern = filaments.filter((f) => f.confidence != null).length;
  const cardList = (place) =>
    cards.map((card, i) => (
      <Card
        key={card.symbol}
        card={card}
        selected={card.symbol === selectedSymbol}
        onSelect={onSelect}
        style={place?.(i)}
      />
    ));

  return (
    <div ref={boxRef} className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width, maxWidth: "100%" }}>
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
        {aside && (
          <div role="group" aria-label="Dernières décisions">
            {cardList((i) => ({ position: "absolute", right: 0, top: cardsTop + i * CARD_STEP, width: cardWidth }))}
          </div>
        )}
      </div>
      <p className="m-0 text-center text-[11px]" style={{ color: "var(--text-dim)" }}>
        Antenne = confiance de la figure · couleur = décision (vert achat ou renfort, orange surveiller, rouge alléger,
        bleu aucune) · les autres fils sont décoratifs
      </p>
      <button type="button" className="gd-btn" onClick={() => setSpinning((on) => !on)}>
        {spinning ? "Mettre en pause" : "Faire tourner"}
      </button>
      {!aside && cards.length > 0 && (
        <div role="group" aria-label="Dernières décisions" className="grid w-full gap-2">
          {cardList()}
        </div>
      )}
    </div>
  );
}
