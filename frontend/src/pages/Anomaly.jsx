import { useCallback, useMemo } from 'react';
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonCard,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { SEVERITY_TONE } from '../lib/constants';
import { titleCase } from '../lib/format';

export function Anomaly() {
  useDocumentTitle('Anomaly Detection');
  const fetcher = useCallback(({ signal }) => api.ai.anomalyDetect({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  // Memoised so the identity is stable; a fresh `?? []` on every render
  // would invalidate the dependent useMemo each time.
  const anomalies = useMemo(() => data?.anomalies ?? [], [data]);

  const counts = useMemo(() => {
    const tally = { high: 0, medium: 0, low: 0 };
    for (const anomaly of anomalies) {
      const severity = anomaly.severity ?? 'medium';
      if (severity in tally) tally[severity] += 1;
    }
    return tally;
  }, [anomalies]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Tools"
        title="Anomaly Detection"
        description="Isolation Forest and threshold detectors over provider performance, stock movement and request volume."
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
        <>
          <SkeletonCard rows={2} />
          <SkeletonCard rows={5} />
        </>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <SeverityTile label="High severity" count={counts.high} tone="red" />
            <SeverityTile label="Medium severity" count={counts.medium} tone="amber" />
            <SeverityTile label="Low severity" count={counts.low} tone="emerald" />
          </div>

          {data?.summary || data?.explanation ? (
            <Card>
              <CardBody>
                <p className="ai-reasoning-box text-[0.8125rem] leading-relaxed">
                  {data.summary ?? data.explanation}
                </p>
              </CardBody>
            </Card>
          ) : null}

          <Card className="overflow-hidden">
            <CardHeader
              title="Detected Anomalies"
              subtitle={`${anomalies.length} flagged`}
              icon="alert"
            />
            {anomalies.length === 0 ? (
              <EmptyState
                icon="check"
                title="Nothing anomalous"
                description="All monitored signals are within their expected ranges. This panel populates when a detector flags an outlier."
              />
            ) : (
              <ul className="divide-y divide-[var(--rn-border)]">
                {anomalies.map((anomaly, index) => (
                  <li key={index} className="flex gap-3 px-5 py-4">
                    <span
                      className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                        anomaly.severity === 'high'
                          ? 'bg-red-500/10 text-red-500'
                          : anomaly.severity === 'low'
                            ? 'bg-emerald-500/10 text-emerald-500'
                            : 'bg-amber-500/10 text-amber-500'
                      }`}
                      aria-hidden="true"
                    >
                      <Icon name="alert" className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={SEVERITY_TONE[titleCase(anomaly.severity ?? 'medium')] ?? 'amber'}>
                          {anomaly.severity ?? 'medium'}
                        </Badge>
                        {anomaly.type ? (
                          <span className="mono text-[0.6875rem] text-[var(--rn-text-3)]">
                            {anomaly.type}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-[var(--rn-text)]">
                        {anomaly.message ?? anomaly.description ?? 'Unusual pattern detected.'}
                      </p>
                      {anomaly.explanation ? (
                        <p className="mt-1 text-xs leading-relaxed text-[var(--rn-text-3)]">
                          {anomaly.explanation}
                        </p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function SeverityTile({ label, count, tone }) {
  const tones = {
    red: 'text-red-500',
    amber: 'text-amber-500',
    emerald: 'text-emerald-500',
  };
  return (
    <div className="dash-card p-5">
      <p className="kpi-label">{label}</p>
      <p className={`mt-1.5 text-2xl font-bold tabular-nums ${tones[tone]}`}>{count}</p>
    </div>
  );
}
