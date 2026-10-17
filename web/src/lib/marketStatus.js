// Statut de séance Euronext Paris, calculé côté client à l'heure de Paris
// (Europe/Paris, heure d'été incluse) : séance continue 9h00-17h30 du lundi au
// vendredi, hors jours de fermeture Euronext (1er janvier, Vendredi saint,
// lundi de Pâques, 1er mai, 25 et 26 décembre). Les séances raccourcies
// (24 et 31 décembre, clôture 14h05) sont prises en compte.

const OPEN_MINUTES = 9 * 60;
const CLOSE_MINUTES = 17 * 60 + 30;
const SHORT_CLOSE_MINUTES = 14 * 60 + 5;

// Dimanche de Pâques (algorithme grégorien anonyme), mois 1-12.
export function easterSunday(year) {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31);
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return { month, day };
}

function shiftDay(year, month, day, delta) {
  const dt = new Date(Date.UTC(year, month - 1, day + delta));
  return { month: dt.getUTCMonth() + 1, day: dt.getUTCDate() };
}

export function isEuronextHoliday(year, month, day) {
  const fixed = [
    [1, 1],
    [5, 1],
    [12, 25],
    [12, 26],
  ];
  if (fixed.some(([m, d]) => m === month && d === day)) return true;
  const easter = easterSunday(year);
  const goodFriday = shiftDay(year, easter.month, easter.day, -2);
  const easterMonday = shiftDay(year, easter.month, easter.day, 1);
  return [goodFriday, easterMonday].some((x) => x.month === month && x.day === day);
}

// Date/heure à Paris pour un instant donné.
export function parisParts(date) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    weekday: "short",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value;
  return {
    year: Number(get("year")),
    month: Number(get("month")),
    day: Number(get("day")),
    hour: Number(get("hour")),
    minute: Number(get("minute")),
    weekday: get("weekday"), // Mon, Tue, … Sun
  };
}

export function marketStatus(date = new Date()) {
  const p = parisParts(date);
  const time = `${String(p.hour).padStart(2, "0")}:${String(p.minute).padStart(2, "0")}`;
  const minutes = p.hour * 60 + p.minute;
  if (p.weekday === "Sat" || p.weekday === "Sun") {
    return { open: false, label: "Marché fermé", reason: "week-end", time };
  }
  if (isEuronextHoliday(p.year, p.month, p.day)) {
    return { open: false, label: "Marché fermé", reason: "jour férié", time };
  }
  const shortDay = p.month === 12 && (p.day === 24 || p.day === 31);
  const close = shortDay ? SHORT_CLOSE_MINUTES : CLOSE_MINUTES;
  if (minutes < OPEN_MINUTES) {
    return { open: false, label: "Marché fermé", reason: "ouverture à 09:00", time };
  }
  if (minutes >= close) {
    return { open: false, label: "Marché fermé", reason: "séance terminée", time };
  }
  return { open: true, label: "Marché ouvert", reason: null, time };
}
