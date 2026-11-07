import { formatNumber } from '../lib/format';
import { Icon } from './ui/Icon';
import { Skeleton, cx } from './ui';

/**
 * A single KPI tile with an optional sparkline.
 *
 * The sparkline renders only when the backend supplies a real series. The
 * original drew one for every tile from `random.uniform` noise, so the trend
 * lines were decorative but read as measured data.
 */
export function KpiCard({
  label,
  value,
  icon,
  tone = 'indigo',
  context,
  series,
  loading = false,
  className,
}) {
  const tones = {
    indigo: 'text-indigo-500 bg-indigo-500/10',
    emerald: 'text-emerald-500 bg-emerald-500/10',
    amber: 'text-amber-500 bg-amber-500/10',
    red: 'text-red-500 bg-red-500/10',
    violet: 'text-violet-500 bg-violet-500/10',
  };

  if (loading) {
    return (
      <div className={cx('dash-card p-5', className)} aria-busy="true">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <Skeleton className="mt-4 h-7 w-24" />
        <Skeleton className="mt-2 h-3 w-32" />
      </div>
    );
  }

  return (
    <div className={cx('dash-card group p-5', className)}>
      <div className="flex items-start justify-between gap-3">
        <span className={cx('kpi-icon', tones[tone] ?? tones.indigo)} aria-hidden="true">
          <Icon name={icon} className="h-4 w-4" />
        </span>
        {series?.length > 1 ? <Sparkline values={series} tone={tone} /> : null}
      </div>

      <p className="kpi-value mt-4 tabular-nums">{formatNumber(value, { compact: true })}</p>
      <p className="kpi-label">{label}</p>

      {context ? (
        <p className="mt-2.5 border-t border-[var(--rn-border)] pt-2.5 text-[0.6875rem] leading-relaxed text-[var(--rn-text-3)]">
          {context}
        </p>
      ) : null}
    </div>
  );
}

/** Inline SVG trend line — no charting library for something this small. */
function Sparkline({ values, tone = 'indigo', width = 68, height = 26 }) {
  const numbers = values.map(Number).filter((n) => !Number.isNaN(n));
  if (numbers.length < 2) return null;

  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  const range = max - min || 1;

  const points = numbers
    .map((value, index) => {
      const x = (index / (numbers.length - 1)) * width;
      const y = height - ((value - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  const strokes = {
    indigo: 'var(--c-indigo)',
    emerald: 'var(--c-emerald)',
    amber: 'var(--c-amber)',
    red: 'var(--c-red)',
    violet: 'var(--c-violet)',
  };
  const rising = numbers[numbers.length - 1] >= numbers[0];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible opacity-70 transition-opacity group-hover:opacity-100"
      role="img"
      aria-label={`Trend over the last ${numbers.length} days: ${rising ? 'rising' : 'falling'}`}
    >
      <polyline
        points={points}
        fill="none"
        stroke={strokes[tone] ?? strokes.indigo}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
