// Pure chart geometry: no DOM, no health logic. Unit-tested with node --test.

/** "Nice" round number near `range` (Heckbert's algorithm). */
function niceNumber(range, round) {
  const exponent = Math.floor(Math.log10(range));
  const fraction = range / 10 ** exponent;
  let nice;
  if (round) nice = fraction < 1.5 ? 1 : fraction < 3 ? 2 : fraction < 7 ? 5 : 10;
  else nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * 10 ** exponent;
}

/** Tick values covering [min, max] with round steps. */
export function niceTicks(min, max, maxTicks = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { ticks: [], min: 0, max: 1 };
  if (min === max) { min -= 1; max += 1; }
  const step = niceNumber(niceNumber(max - min, false) / Math.max(maxTicks - 1, 1), true);
  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = niceMin; v <= niceMax + step / 2; v += step) ticks.push(Number(v.toFixed(10)));
  return { ticks, min: niceMin, max: niceMax };
}

/** Linear map domain -> range; a zero-width domain maps to the middle of the range. */
export function linearScale(d0, d1, r0, r1) {
  if (d0 === d1) return () => (r0 + r1) / 2;
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}

/** 'YYYY-MM-DD' -> whole days since the Unix epoch (UTC, so no DST/timezone drift). */
export function dayNumber(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}

export function isoFromDayNumber(day) {
  return new Date(day * 86_400_000).toISOString().slice(0, 10);
}

/** Up to `count` evenly spaced whole-day ticks between two day numbers. */
export function dayTicks(minDay, maxDay, count = 4) {
  if (minDay === maxDay) return [minDay];
  const ticks = new Set();
  for (let i = 0; i < count; i += 1) ticks.add(Math.round(minDay + ((maxDay - minDay) * i) / (count - 1)));
  return [...ticks];
}

export function pathFromPoints(points) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
}

/** Clip open-ended bands (min/max may be null) to the visible y-domain; drop those outside it. */
export function visibleBands(bands, domainMin, domainMax) {
  const out = [];
  for (const band of bands ?? []) {
    const low = Math.max(band.min ?? -Infinity, domainMin);
    const high = Math.min(band.max ?? Infinity, domainMax);
    if (high > low) out.push({ category: band.category, label: band.label, low, high });
  }
  return out;
}

/** y-domain covering data (+ optional extra values like a target line) with 8% headroom. */
export function paddedExtent(values, extras = []) {
  const all = [...values, ...extras].filter(Number.isFinite);
  if (all.length === 0) return { min: 0, max: 1 };
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = (hi - lo || Math.abs(hi) * 0.1 || 1) * 0.08;
  return { min: lo - pad, max: hi + pad };
}
