// PRNG déterministe (seedé par ticker) pour générer des bougies OHLC stables entre deux rendus.
function seededRandom(seed) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return function () {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function seedFromString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h || 1;
}

export function generateOHLC(trendPoints, seedKey, n = 26) {
  const rnd = seededRandom(seedFromString(seedKey));
  const base = trendPoints[trendPoints.length - 1];
  const spanFactor = Math.max(...trendPoints) - Math.min(...trendPoints) || 1;
  let last = base - spanFactor * 0.6;
  const candles = [];
  for (let i = 0; i < n; i++) {
    const drift = (trendPoints[Math.min(i, trendPoints.length - 1)] - trendPoints[0]) / trendPoints.length;
    const open = last;
    const vol = spanFactor * 0.18 + spanFactor * 0.12 * rnd();
    const close = open + drift * 0.35 + (rnd() - 0.45) * vol;
    const high = Math.max(open, close) + rnd() * vol * 0.6;
    const low = Math.min(open, close) - rnd() * vol * 0.6;
    candles.push({ open, high, low, close });
    last = close;
  }
  return candles;
}
