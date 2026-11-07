import { useCallback, useMemo, useState } from 'react';
import { InsightList } from '../components/InsightList';
import {
  Button,
  Card,
  CardHeader,
  ErrorState,
  PageHeader,
  SkeletonCard,
} from '../components/ui';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'critical', label: 'Critical' },
  { value: 'warning', label: 'Warning' },
  { value: 'info', label: 'Info' },
];

export function Insights() {
  useDocumentTitle('AI Insights');
  const [filter, setFilter] = useState('all');

  const fetcher = useCallback(({ signal }) => api.ai.insights({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  // Memoised so the identity is stable; a fresh `?? []` on every render
  // would invalidate the dependent useMemo each time.
  const insights = useMemo(() => data?.insights ?? [], [data]);
  const counts = useMemo(() => {
    const tally = { all: insights.length, critical: 0, warning: 0, info: 0 };
    for (const insight of insights) {
      const severity = insight?.severity ?? 'info';
      if (severity in tally) tally[severity] += 1;
    }
    return tally;
  }, [insights]);

  const visible = filter === 'all' ? insights : insights.filter((i) => i.severity === filter);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Insight Feed"
        description="Actionable observations generated from forecast, risk, anomaly and stock signals."
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={refresh} loading={loading}>
            Refresh
          </Button>
        }
      />

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={refresh} />
        </Card>
      ) : loading ? (
        <SkeletonCard rows={6} />
      ) : (
        <Card className="overflow-hidden">
          <CardHeader
            title="Insights"
            subtitle={data?.summary}
            icon="bulb"
            action={
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by severity">
                {FILTERS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setFilter(option.value)}
                    aria-pressed={filter === option.value}
                    className={`rounded-full px-2.5 py-1 text-[0.6875rem] font-semibold transition-colors ${
                      filter === option.value
                        ? 'bg-indigo-500 text-white'
                        : 'bg-[var(--rn-border)]/60 text-[var(--rn-text-2)] hover:bg-[var(--rn-border)]'
                    }`}
                  >
                    {option.label}
                    <span className="ml-1 opacity-70 tabular-nums">{counts[option.value]}</span>
                  </button>
                ))}
              </div>
            }
          />
          <InsightList
            insights={visible}
            emptyMessage={
              filter === 'all'
                ? 'Nothing requires attention right now.'
                : `No ${filter} insights at the moment.`
            }
          />
        </Card>
      )}

      {data?.explanation ? (
        <Card>
          <CardHeader title="How these are generated" icon="info" />
          <div className="p-5">
            <p className="text-xs leading-relaxed text-[var(--rn-text-2)]">{data.explanation}</p>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
