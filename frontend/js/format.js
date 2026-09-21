// Presentation-only helpers: number/date formatting. No health rules live in the browser.
const LOCALE = 'en-GB';

export function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

/** '2026-09-05' -> Date at UTC midnight (no timezone drift). */
export function parseISODate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function formatDate(iso, { year = false } = {}) {
  if (!iso) return '—';
  return new Intl.DateTimeFormat(LOCALE, { day: '2-digit', month: 'short', year: year ? 'numeric' : undefined, timeZone: 'UTC' }).format(parseISODate(iso));
}

/** '2026-09' -> 'Sep 2026' */
export function formatMonth(ym) {
  const [y, m] = ym.split('-').map(Number);
  return new Intl.DateTimeFormat(LOCALE, { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(y, m - 1, 1)));
}

export function signed(value, digits = 1) {
  if (value === null || value === undefined) return '—';
  const text = formatNumber(Math.abs(value), digits);
  if (value > 0) return `+${text}`;
  if (value < 0) return `−${text}`;
  return text;
}

/** The user's own calendar date (not UTC) as YYYY-MM-DD, for date inputs. */
export function todayLocalISO(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
