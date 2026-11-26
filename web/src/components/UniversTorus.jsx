import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { decisionColor } from "../data";
import { useElementWidth } from "../hooks/useElementWidth";
import { eur } from "../lib/format";
import {
  buildCards,
  buildFilaments,
  buildItems,
  buildPatternCards,
  buildStrands,
  makeProjector,
  nearestFilament,
} from "./torusLayout";

// Tore 3D de l'univers (écran Univers).
//
// - Chaque valeur suivie = une boucle autour du tube et une antenne sur le bord
//   extérieur, rangées par famille de secteur (buildItems).
// - Longueur de l'antenne = confiance de la dernière figure détectée ; couleur
//   = décision en cours (bleu sans décision). La valeur sélectionnée est
//   surlignée en blanc.
// - Les autres fils sont décoratifs et ne représentent aucune donnée.
// - Deux listes de cartes encadrent le tore quand la place le permet : à gauche
//   les valeurs dont la dernière figure a la plus forte confiance, à droite les
//   décisions enregistrées. Chaque carte est reliée à son antenne par une courbe ;
//   faute de place, une liste passe sous le tore, sans courbe. Au-delà de dix,
//   une liste défile en boucle (une carte toutes les FEED_MS), comme un flux de
//   transactions ; chaque carte garde sa date. Un clic sur une carte sélectionne
//   la valeur.
//
// Le tore tourne sur son axe (celui du trou). Glisser horizontalement le fait
// tourner, verticalement incline la vue ; un clic près d'une antenne
// sélectionne la valeur. Au clavier : les cartes ou le menu « Choisir une
// valeur ». Le bouton de pause arrête la rotation et les listes, qui ne démarrent
// pas si le système demande moins d'animations. Les listes attendent aussi tant
// que le pointeur ou le focus clavier est sur l'une d'elles, pour que la carte
// visée ne bouge pas.
//
// Dessiné sur un <canvas> 2D (perspective calculée à la main) : quelques
// milliers de segments par image, sans bibliothèque 3D.

const STRANDS = buildStrands();
const SPIN = 0.18; // radians par seconde
const DRAG = 0.008; // radians par pixel glissé
const CLICK_SLOP = 5; // au-delà, le geste est un glisser, pas un clic
const MAX_TILT = 1.35;
const CARDS_FROM = 600; // largeur à partir de laquelle les décisions sont à droite
const BOTH_FROM = 980; // largeur à partir de laquelle les figures sont à gauche
const HEADING = 22; // place du titre au-dessus d'une liste placée à côté
const CARD_COUNT = 10;
const CARD_HEIGHT = 58;
const CARD_STEP = CARD_HEIGHT + 8;
const LINK_GAP = 24; // espace réservé aux courbes devant les cartes
const FEED_MS = 3000; // délai entre deux cartes d'une liste
const SLIDE_MS = 450; // durée du glissement d'une carte à la suivante

const decisionTint = (decision) => (decision ? decisionColor(decision) : "var(--accent)");
const listHeight = (cards) => (cards.length ? cards.length * CARD_STEP - 8 : 0);

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

function keyboardFocus(element) {
  try {
    return element.matches(":focus-visible");
  } catch {
    return true; // sélecteur inconnu : on met le fil en attente par prudence
  }
}

// `remaining` va de 1 (une carte vient d'entrer) à 0 (fil en place) : toutes les
// cartes sont encore décalées vers le haut d'autant, la première apparaît.
function placeFeed(list, remaining) {
  if (!list) return;
  list.style.transform = remaining ? `translateY(${-CARD_STEP * remaining}px)` : "";
  Array.from(list.children).forEach((card, i) => {
    card.style.opacity = i === 0 && remaining ? String(1 - remaining) : "";
  });
}

function stroke(ctx, project, points) {
  points.forEach((point, i) => {
    const { x, y } = project(point);
    if (i) ctx.lineTo(x, y);
    else ctx.moveTo(x, y);
  });
}

function draw(canvas, ctx, { filaments, selectedSymbol, links, remaining, view, width, height, torusLeft, torusWidth }) {
  // Le tore occupe le milieu du canvas ; les courbes vont vers les listes.
  const project = makeProjector({ ...view, left: torusLeft, width: torusWidth, height });
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

  // Les liens : une courbe par carte, de son antenne au bord de la carte.
  for (const link of links) {
    // La courbe suit sa carte pendant le glissement (liste qui défile).
    const slid = link.scrolls ? remaining : 0;
    const endY = link.y - CARD_STEP * slid;
    const tip = project(link.tip);
    const chosen = link.symbol === selectedSymbol;
    const tint = color(decisionTint(link.decision));
    ctx.strokeStyle = tint;
    ctx.fillStyle = tint;
    // Antenne passée derrière le tore : courbe atténuée.
    ctx.globalAlpha = (chosen ? 1 : 0.7) * (tip.depth > 0 ? 1 : 0.5) * (link.first ? 1 - slid : 1);
    ctx.lineWidth = chosen ? 2.4 : 1.2;
    ctx.beginPath();
    ctx.moveTo(tip.x, tip.y);
    ctx.bezierCurveTo(tip.x + (link.x - tip.x) * 0.6, tip.y, link.x - 60 * link.side, endY, link.x, endY);
    ctx.stroke();
    for (const [x, y] of [
      [tip.x, tip.y],
      [link.x, endY],
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

function Card({ card, selected, onSelect, style, badge, line, note }) {
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
        <span className="truncate">{badge}</span>
      </span>
      <span className="truncate" title={line}>
        {line}
      </span>
      <span className="truncate" style={{ color: "var(--text-dim)" }}>
        {note}
      </span>
    </button>
  );
}

const decisionContent = ({ decision, detail }) => ({
  badge: decision ?? "aucune décision",
  line: `TP ${eur(detail.take_profit)} · SL ${eur(detail.stop_loss)}`,
  note: `Entrée ${eur(detail.entry_price)} · ${shortDate(detail.created_at)}`,
});

// La décision est écrite : la couleur de la carte ne suffit pas à la dire.
const patternContent = ({ decision, confidence, rank, detail }) => ({
  badge: [decision, `${Math.round(confidence)} %`].filter(Boolean).join(" · "),
  line: detail.pattern_type,
  note: `n° ${rank} · détectée le ${shortDate(detail.detected_at)}`,
});

function Heading({ children, style }) {
  return (
    <h2 className="gd-label m-0 truncate" style={style}>
      {children}
    </h2>
  );
}

export default function UniversTorus({ securities, patternsBySymbol, decisionsMap, selectedSymbol, onSelect }) {
  const filaments = useMemo(
    () => buildFilaments(buildItems(securities, patternsBySymbol, decisionsMap)),
    [securities, patternsBySymbol, decisionsMap]
  );
  const [step, setStep] = useState(0); // nombre de cartes entrées dans chaque liste
  const decisionCards = useMemo(
    () => buildCards(filaments, decisionsMap, CARD_COUNT, step),
    [filaments, decisionsMap, step]
  );
  const patternCards = useMemo(
    () => buildPatternCards(filaments, patternsBySymbol, CARD_COUNT, step),
    [filaments, patternsBySymbol, step]
  );
  const decisionsScroll = useMemo(
    () => filaments.filter((f) => decisionsMap?.[f.symbol]).length > CARD_COUNT,
    [filaments, decisionsMap]
  );
  const patternsScroll = useMemo(() => filaments.filter((f) => f.confidence != null).length > CARD_COUNT, [filaments]);
  const scrolls = decisionsScroll || patternsScroll;
  const [boxRef, boxWidth] = useElementWidth();
  const width = boxWidth ?? 640;
  const rightAside = width >= CARDS_FROM && decisionCards.length > 0;
  const leftAside = width >= BOTH_FROM && patternCards.length > 0;
  const cardWidth = Math.round(Math.min(270, width * (width >= BOTH_FROM ? 0.23 : 0.34)));
  const torusLeft = leftAside ? cardWidth + LINK_GAP : 0;
  const torusWidth = width - torusLeft - (rightAside ? cardWidth + LINK_GAP : 0);
  const rightHeight = rightAside ? listHeight(decisionCards) : 0;
  const leftHeight = leftAside ? listHeight(patternCards) : 0;
  const tallest = Math.max(rightHeight, leftHeight);
  const height = Math.round(Math.max(Math.min(torusWidth, 640), tallest ? tallest + 2 * HEADING : 0));
  const rightTop = Math.round((height - rightHeight) / 2);
  const leftTop = Math.round((height - leftHeight) / 2);
  const links = useMemo(() => {
    // `side` : 1 pour une liste à droite du tore, -1 à gauche.
    const toLinks = (cards, { x, top, side, scrolls }) =>
      cards.map((card, i) => ({
        symbol: card.symbol,
        decision: card.decision,
        tip: card.tip,
        x,
        y: top + i * CARD_STEP + CARD_HEIGHT / 2,
        side,
        scrolls,
        first: i === 0,
      }));
    return [
      ...(leftAside ? toLinks(patternCards, { x: cardWidth, top: leftTop, side: -1, scrolls: patternsScroll }) : []),
      ...(rightAside
        ? toLinks(decisionCards, { x: width - cardWidth, top: rightTop, side: 1, scrolls: decisionsScroll })
        : []),
    ];
  }, [
    leftAside,
    rightAside,
    patternCards,
    decisionCards,
    patternsScroll,
    decisionsScroll,
    width,
    cardWidth,
    leftTop,
    rightTop,
  ]);
  const canvasRef = useRef(null);
  const view = useRef({ spin: 0, yaw: -0.7, tilt: 0.25 });
  const drag = useRef(null);
  const redrawRef = useRef(() => {});
  const [running, setRunning] = useState(() => !reducedMotion());
  // Disposition dans laquelle le pointeur ou le focus est entré : si les listes
  // changent de place, l'ancienne attente ne compte plus.
  const layout = `${leftAside}-${rightAside}`;
  const [hoveredIn, setHoveredIn] = useState(null);
  const [focusedIn, setFocusedIn] = useState(null);
  const held = hoveredIn === layout || focusedIn === layout;
  const decisionListRef = useRef(null);
  const patternListRef = useRef(null);
  const slideStart = useRef(null);
  const placeFeeds = useCallback(
    (remaining) => {
      placeFeed(decisionListRef.current, decisionsScroll ? remaining : 0);
      placeFeed(patternListRef.current, patternsScroll ? remaining : 0);
    },
    [decisionsScroll, patternsScroll]
  );

  useEffect(() => {
    if (!running || held || !scrolls) return;
    const timer = setInterval(() => setStep((n) => n + 1), FEED_MS);
    return () => clearInterval(timer);
  }, [running, held, scrolls]);

  // Avant l'affichage : la nouvelle carte part du haut, sans saut visible.
  useLayoutEffect(() => {
    if (!step) return;
    slideStart.current = performance.now();
    placeFeeds(1);
  }, [step, placeFeeds]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const slide = (now) => {
      const start = slideStart.current;
      const progress = !running || start == null ? 1 : Math.min(Math.max((now - start) / SLIDE_MS, 0), 1);
      const remaining = (1 - progress) ** 3; // ralentit en arrivant
      placeFeeds(remaining);
      return remaining;
    };
    const redraw = (now = performance.now()) => {
      const remaining = slide(now);
      const box = { width, height, torusLeft, torusWidth, view: view.current };
      draw(canvas, ctx, { ...box, filaments, selectedSymbol, links, remaining });
    };
    redrawRef.current = redraw;
    redraw();
    if (!running) return;
    let frame;
    let previous = null;
    const tick = (now) => {
      // Écart borné : au retour sur l'onglet, le tore ne saute pas.
      if (previous != null && !drag.current) view.current.spin += (Math.min(now - previous, 100) / 1000) * SPIN;
      previous = now;
      // Le fil peut rester à l'écran sans le tore (téléphone) : ses cartes
      // continuent de glisser même quand on ne dessine plus.
      if (visible) redraw(now);
      else slide(now);
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
  }, [filaments, selectedSymbol, links, width, height, torusLeft, torusWidth, running, placeFeeds]);

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
      makeProjector({ ...view.current, left: torusLeft, width: torusWidth, height }),
      event.clientX - rect.left,
      event.clientY - rect.top
    );
    if (hit) onSelect(hit.symbol);
  }

  const withPattern = filaments.filter((f) => f.confidence != null).length;
  const cardList = (cards, content, place) =>
    cards.map((card, i) => (
      <Card
        key={card.symbol}
        card={card}
        selected={card.symbol === selectedSymbol}
        onSelect={onSelect}
        style={place?.(i)}
        {...content(card)}
      />
    ));

  const feedProps = (ref, label) => ({
    ref,
    role: "group",
    "aria-label": label,
    onPointerEnter: () => setHoveredIn(layout),
    onPointerLeave: () => setHoveredIn(null),
    // Un clic donne aussi le focus : seul le focus clavier arrête les listes.
    onFocus: (event) => setFocusedIn(keyboardFocus(event.target) ? layout : null),
    onBlur: (event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setFocusedIn(null);
    },
  });

  const patternList = { cards: patternCards, content: patternContent, ref: patternListRef, label: "Meilleures figures" };
  const decisionList = {
    cards: decisionCards,
    content: decisionContent,
    ref: decisionListRef,
    label: "Dernières décisions",
  };

  const besideList = ({ cards, content, ref, label }, { left, top, listSize }) => (
    <>
      <Heading style={{ position: "absolute", left, top: top - HEADING, width: cardWidth }}>{label}</Heading>
      <div {...feedProps(ref, label)} style={{ position: "absolute", left, top, width: cardWidth, height: listSize }}>
        {cardList(cards, content, (i) => ({ position: "absolute", left: 0, top: i * CARD_STEP, width: cardWidth }))}
      </div>
    </>
  );

  const belowList = ({ cards, content, ref, label }) => (
    <div className="flex w-full flex-col gap-1">
      <Heading>{label}</Heading>
      <div className="w-full overflow-hidden p-1">
        <div {...feedProps(ref, label)} className="grid w-full gap-2">
          {cardList(cards, content)}
        </div>
      </div>
    </div>
  );

  return (
    <div ref={boxRef} className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width, maxWidth: "100%" }}>
        {leftAside && besideList(patternList, { left: 0, top: leftTop, listSize: leftHeight })}
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
        {rightAside && besideList(decisionList, { left: width - cardWidth, top: rightTop, listSize: rightHeight })}
      </div>
      <p className="m-0 text-center text-[11px]" style={{ color: "var(--text-dim)" }}>
        Antenne = confiance de la figure · couleur = décision (vert achat ou renfort, orange surveiller, rouge alléger,
        bleu aucune) · les autres fils sont décoratifs{scrolls && " · les listes de plus de dix valeurs défilent en boucle"}
      </p>
      <button type="button" className="gd-btn" onClick={() => setRunning((on) => !on)}>
        {running ? "Mettre en pause" : "Reprendre l'animation"}
      </button>
      {!rightAside && decisionCards.length > 0 && belowList(decisionList)}
      {!leftAside && patternCards.length > 0 && belowList(patternList)}
    </div>
  );
}
