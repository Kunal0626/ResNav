/** Shared display formatters. Locale-aware, null-safe, and used everywhere so
 *  numbers read the same on every screen. */

const numberFormatter = new Intl.NumberFormat('en-IN');
// Deliberately en-US for compact notation: en-IN renders 110,000 as "1.1L",
// which reads as "litres" in an app whose units include litres and kilograms.
const compactFormatter = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

export function formatNumber(value, { compact = false, fallback = '—' } = {}) {
  const n = Number(value);
  if (value === null || value === undefined || Number.isNaN(n)) return fallback;
  return compact && Math.abs(n) >= 10000 ? compactFormatter.format(n) : numberFormatter.format(n);
}

export function formatPercent(value, { digits = 0, fallback = '—' } = {}) {
  const n = Number(value);
  if (Number.isNaN(n)) return fallback;
  return `${n.toFixed(digits)}%`;
}

export function formatDistance(km) {
  const n = Number(km);
  if (Number.isNaN(n)) return '—';
  return n < 1 ? `${Math.round(n * 1000)} m` : `${n.toFixed(1)} km`;
}

/** Absolute timestamp, e.g. "2 Aug 2026, 14:05". */
export function formatDateTime(value, { fallback = '—' } = {}) {
  if (!value) return fallback;
  // SQLite emits "YYYY-MM-DD HH:MM:SS", which Safari refuses to parse as-is.
  const date = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Relative time, e.g. "3 hours ago". Falls back to the absolute date if old. */
export function formatRelative(value) {
  if (!value) return '—';
  const date = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return String(value);

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  if (Math.abs(seconds) < 60) return 'just now';

  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  for (const [unit, secondsPerUnit] of units) {
    if (Math.abs(seconds) >= secondsPerUnit) {
      return rtf.format(-Math.round(seconds / secondsPerUnit), unit);
    }
  }
  return formatDateTime(value);
}

/** "Stable" and numeric day counts both arrive from the forecast API. */
export function formatDays(value) {
  if (value === null || value === undefined) return '—';
  const n = Number(value);
  return Number.isNaN(n) ? String(value) : `${n.toFixed(1)} days`;
}

export function titleCase(value) {
  if (!value) return '';
  return String(value).charAt(0).toUpperCase() + String(value).slice(1);
}
