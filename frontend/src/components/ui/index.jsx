/**
 * Shared primitives, built on the existing `resnav.css` classes so the visual
 * language is unchanged — these replace markup that was copy-pasted across
 * twenty Jinja templates.
 */

import { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from './Icon';

const cx = (...parts) => parts.filter(Boolean).join(' ');

/* ── Card ─────────────────────────────────────────────────── */

export function Card({ className, children, as: Tag = 'section', ...rest }) {
  return (
    <Tag className={cx('dash-card', className)} {...rest}>
      {children}
    </Tag>
  );
}

export function CardHeader({ title, subtitle, icon, action, className }) {
  return (
    <div
      className={cx(
        'flex flex-wrap items-start justify-between gap-3 border-b border-[var(--rn-border)] px-5 py-4',
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-500 dark:text-indigo-400"
            aria-hidden="true"
          >
            <Icon name={icon} className="h-4 w-4" />
          </span>
        ) : null}
        <div className="min-w-0">
          <h2 className="truncate text-[0.9375rem] font-semibold text-[var(--rn-text)]">{title}</h2>
          {subtitle ? (
            <p className="mt-0.5 text-xs leading-relaxed text-[var(--rn-text-3)]">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function CardBody({ className, children }) {
  return <div className={cx('p-5', className)}>{children}</div>;
}

/* ── Button ───────────────────────────────────────────────── */

const BUTTON_VARIANTS = {
  primary: 'rn-btn rn-btn-primary',
  ai: 'rn-btn rn-btn-ai',
  ghost: 'rn-btn rn-btn-ghost',
  danger: 'rn-btn rn-btn-danger',
  quiet: 'rn-btn',
};

export const Button = forwardRef(function Button(
  {
    variant = 'quiet',
    size,
    loading = false,
    disabled,
    icon,
    iconPosition = 'left',
    className,
    children,
    to,
    href,
    type = 'button',
    ...rest
  },
  ref,
) {
  const classes = cx(
    BUTTON_VARIANTS[variant] ?? BUTTON_VARIANTS.quiet,
    size === 'sm' && 'rn-btn-sm',
    (disabled || loading) && 'pointer-events-none opacity-55',
    className,
  );

  const content = (
    <>
      {loading ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : icon && iconPosition === 'left' ? (
        <Icon name={icon} className="h-4 w-4" aria-hidden="true" />
      ) : null}
      {children}
      {!loading && icon && iconPosition === 'right' ? (
        <Icon name={icon} className="h-4 w-4" aria-hidden="true" />
      ) : null}
    </>
  );

  if (to) {
    return (
      <Link ref={ref} to={to} className={classes} {...rest}>
        {content}
      </Link>
    );
  }
  if (href) {
    return (
      <a ref={ref} href={href} className={classes} target="_blank" rel="noreferrer" {...rest}>
        {content}
      </a>
    );
  }
  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {content}
    </button>
  );
});

/* ── Badge ────────────────────────────────────────────────── */

export function Badge({ tone = 'slate', dot = false, className, children }) {
  return (
    <span className={cx('badge', `badge-${tone}`, className)}>
      {dot ? <span className="badge-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

/* ── Spinner ──────────────────────────────────────────────── */

export function Spinner({ className, label }) {
  return (
    <>
      <svg
        className={cx('animate-spin', className || 'h-4 w-4')}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path
          className="opacity-90"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z"
        />
      </svg>
      {label ? <span className="sr-only">{label}</span> : null}
    </>
  );
}

/* ── Skeleton ─────────────────────────────────────────────── */

export function Skeleton({ className }) {
  return <div className={cx('skeleton', className || 'h-4 w-full')} aria-hidden="true" />;
}

export function SkeletonCard({ rows = 3, className }) {
  return (
    <Card className={cx('overflow-hidden', className)} aria-busy="true">
      <div className="border-b border-[var(--rn-border)] px-5 py-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-2 h-3 w-64" />
      </div>
      <div className="space-y-3 p-5">
        {Array.from({ length: rows }, (_, index) => (
          <Skeleton key={index} className={cx('h-3', index % 3 === 2 ? 'w-2/3' : 'w-full')} />
        ))}
      </div>
      <span className="sr-only">Loading…</span>
    </Card>
  );
}

export function SkeletonTable({ rows = 5, columns = 4 }) {
  return (
    <div className="space-y-2 p-5" aria-busy="true">
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div key={rowIndex} className="flex gap-3">
          {Array.from({ length: columns }, (_, columnIndex) => (
            <Skeleton key={columnIndex} className="h-3 flex-1" />
          ))}
        </div>
      ))}
      <span className="sr-only">Loading table data…</span>
    </div>
  );
}

/* ── Empty / error states ─────────────────────────────────── */

export function EmptyState({ icon = 'inbox', title, description, action, className }) {
  return (
    <div className={cx('flex flex-col items-center px-6 py-14 text-center', className)}>
      <span
        className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--rn-border)]/60 text-[var(--rn-text-3)]"
        aria-hidden="true"
      >
        <Icon name={icon} className="h-6 w-6" />
      </span>
      <h3 className="text-sm font-semibold text-[var(--rn-text)]">{title}</h3>
      {description ? (
        <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-[var(--rn-text-3)]">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry, className, title }) {
  const retryable = error?.isRetryable ?? true;
  // A read-only demo refusing a write is working as intended. Showing it in
  // alert red would read as a broken site.
  const limit = error?.isDemoLimit === true;
  // Defaulted per kind, so pages that pass no title say the right thing in
  // the demo without each one needing to know demo mode exists.
  // A demo limit overrides the caller's title on purpose: every page's
  // title says something failed, and nothing did.
  const heading = limit
    ? 'Not available in this demo'
    : (title ?? 'Could not load this data');
  return (
    <div
      role={limit ? 'note' : 'alert'}
      className={cx('flex flex-col items-center px-6 py-14 text-center', className)}
    >
      <span
        className={cx(
          'mb-4 flex h-12 w-12 items-center justify-center rounded-xl',
          limit
            ? 'bg-[var(--rn-surface)] text-[var(--rn-text-2)]'
            : 'bg-red-500/10 text-red-500',
        )}
        aria-hidden="true"
      >
        <Icon name={limit ? 'info' : 'alert'} className="h-6 w-6" />
      </span>
      <h3 className="text-sm font-semibold text-[var(--rn-text)]">{heading}</h3>
      <p className="mt-1.5 max-w-md text-xs leading-relaxed text-[var(--rn-text-3)]">
        {error?.message || 'An unexpected error occurred.'}
      </p>
      {onRetry && retryable ? (
        <Button variant="ghost" size="sm" icon="refresh" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/* ── Table ────────────────────────────────────────────────── */

export function TableWrap({ className, children }) {
  return (
    <div
      className={cx('rn-table-wrap', className)}
      // Horizontal scroll containers must be reachable by keyboard.
      tabIndex={0}
      role="region"
      aria-label="Scrollable table"
    >
      {children}
    </div>
  );
}

export function Table({ className, children }) {
  return <table className={cx('rn-table', className)}>{children}</table>;
}

/* ── Progress ─────────────────────────────────────────────── */

export function Progress({ value, max = 100, tone = 'accent', label, className }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / max) * 100 || 0));
  const colors = {
    accent: 'var(--c-accent)',
    red: 'var(--c-red)',
    amber: 'var(--c-amber)',
    emerald: 'var(--c-emerald)',
  };
  return (
    <div
      className={cx('rn-progress', className)}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className="rn-progress-fill"
        style={{ width: `${pct}%`, background: colors[tone] ?? colors.accent }}
      />
    </div>
  );
}

/* ── Form fields ──────────────────────────────────────────── */

export function Field({ label, htmlFor, hint, error, required, className, children }) {
  return (
    <div className={cx('space-y-1.5', className)}>
      <label className="rn-label" htmlFor={htmlFor}>
        {label}
        {required ? (
          <span className="ml-0.5 text-red-500" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-xs text-red-500" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-xs text-[var(--rn-text-3)]">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export const Input = forwardRef(function Input({ className, invalid, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={cx('rn-input', invalid && 'border-red-500/70', className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
});

export const Select = forwardRef(function Select({ className, children, ...rest }, ref) {
  return (
    <select ref={ref} className={cx('rn-input', className)} {...rest}>
      {children}
    </select>
  );
});

export const Textarea = forwardRef(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cx('rn-input resize-y', className)} {...rest} />;
});

/* ── Page header ──────────────────────────────────────────── */

export function PageHeader({ eyebrow, title, description, actions, className }) {
  return (
    <header className={cx('mb-6 flex flex-wrap items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1.5 text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-indigo-500 dark:text-indigo-400">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-xl font-bold tracking-tight text-[var(--rn-text)] sm:text-2xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--rn-text-2)]">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

export { cx };

export { Portal } from './Portal';
