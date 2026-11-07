import { STATUS_TONE } from '../lib/constants';
import { Badge, EmptyState } from './ui';
import { Icon } from './ui/Icon';

/**
 * Renders insights from either shape the API produces: plain strings (overview)
 * or `{severity, category, message, explanation}` objects (AI modules).
 */
export function InsightList({ insights = [], emptyMessage = 'No insights to report yet.' }) {
  if (!insights.length) {
    return (
      <EmptyState
        icon="bulb"
        title="Nothing to flag"
        description={emptyMessage}
      />
    );
  }

  return (
    <ul className="divide-y divide-[var(--rn-border)]">
      {insights.map((insight, index) => {
        const isObject = typeof insight === 'object' && insight !== null;
        const severity = isObject ? insight.severity : 'info';
        const message = isObject ? insight.message : insight;
        const explanation = isObject ? insight.explanation : null;

        return (
          <li
            key={`${message}-${index}`}
            className="flex gap-3 px-5 py-4 transition-colors hover:bg-[var(--rn-border)]/25"
          >
            <SeverityMark severity={severity} />
            <div className="min-w-0 flex-1">
              <p className="text-[0.8125rem] leading-relaxed text-[var(--rn-text)]">{message}</p>
              {explanation ? (
                <p className="mt-1.5 text-xs leading-relaxed text-[var(--rn-text-3)]">
                  {explanation}
                </p>
              ) : null}
              {isObject && insight.category ? (
                <Badge tone={STATUS_TONE[severity] ?? 'slate'} className="mt-2.5">
                  {insight.category}
                </Badge>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function SeverityMark({ severity }) {
  const marks = {
    critical: { icon: 'alert', className: 'text-red-500 bg-red-500/10' },
    warning: { icon: 'alert', className: 'text-amber-500 bg-amber-500/10' },
    info: { icon: 'info', className: 'text-indigo-500 bg-indigo-500/10' },
  };
  const mark = marks[severity] ?? marks.info;

  return (
    <span
      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${mark.className}`}
      aria-hidden="true"
    >
      <Icon name={mark.icon} className="h-3.5 w-3.5" />
    </span>
  );
}
