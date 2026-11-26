// Invite d'installation. Chrome émet `beforeinstallprompt` une seule fois, tôt,
// souvent avant la connexion : on l'écoute dès le chargement du module.
let deferred = null;
const listeners = new Set();
const notify = () => listeners.forEach((listener) => listener());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    notify();
  });
}

export const getInstallPrompt = () => deferred;

export function subscribeInstallPrompt(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function promptInstall() {
  const event = deferred;
  if (!event) return;
  deferred = null; // une invite ne sert qu'une fois
  notify();
  await event.prompt();
}

export const isStandalone = () =>
  window.navigator.standalone === true || window.matchMedia?.("(display-mode: standalone)").matches === true;

export const isIos = (nav = window.navigator) =>
  /iphone|ipad|ipod/i.test(nav.userAgent) || (nav.platform === "MacIntel" && nav.maxTouchPoints > 1);
