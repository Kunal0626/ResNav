import { useCallback, useMemo } from 'react';
import { Chart } from '../components/charts/Chart';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  Progress,
  SkeletonCard,
  Table,
  TableWrap,
} from '../components/ui';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { SEVERITY_TONE } from '../lib/constants';
import { formatNumber } from '../lib/format';

export function Risk() {
  useDocumentTitle('Risk Prediction');
  const fetcher = useCallback(({ signal }) => api.ai.riskPredict({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  // Memoised so the identity is stable; a fresh `?? []` on every render
  // would invalidate the dependent useMemo each time.
  const zones = useMemo(() => data?.zone_risks ?? [], [data]);

  const chartData = useMemo(() => {
    if (!zones.length) return null;
    return {
      labels: zones.map((zone) => zone.zone_name),
      datasets: [
        {
          label: 'Risk score',
          data: zones.map((zone) => zone.risk_score),
          backgroundColor: zones.map((zone) =>
            zone.risk_score > 66 ? '#ef4444' : zone.risk_score > 33 ? '#f59e0b' : '#10b981',
          ),
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    };
  }, [zones]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Zone Risk Prediction"
        description="Each zone is scored on request volume, average severity, affected population and the share of demand still unmet."
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
          <SkeletonCard rows={3} />
          <SkeletonCard rows={6} />
        </>
      ) : zones.length === 0 ? (
        <Card>
          <EmptyState
            icon="shield"
            title="No zones to score"
            description="Risk scores are derived from resource requests. Create a request to populate this analysis."
            action={
              <Button variant="primary" size="sm" to="/requests" icon="plus">
                Create a request
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          {chartData ? (
            <Card className="overflow-hidden">
              <CardHeader title="Risk by Zone" subtitle="Higher is worse" icon="chart" />
              <div className="p-5">
                <Chart
                  type="bar"
                  data={chartData}
                  height={Math.max(220, zones.length * 42)}
                  ariaLabel="Bar chart of risk score by zone"
                  options={{ indexAxis: 'y', scales: { x: { max: 100 } } }}
                />
              </div>
            </Card>
          ) : null}

          <Card className="overflow-hidden">
            <CardHeader
              title="Zone Breakdown"
              subtitle={data?.summary ?? `${zones.length} zones assessed`}
              icon="shield"
            />
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th scope="col">Zone</th>
                    <th scope="col">Level</th>
                    <th scope="col">Score</th>
                    <th scope="col">Requests</th>
                    <th scope="col">Pending</th>
                    <th scope="col">Population</th>
                  </tr>
                </thead>
                <tbody>
                  {zones.map((zone) => (
                    <tr key={zone.zone_name}>
                      <td className="font-medium text-[var(--rn-text)]">{zone.zone_name}</td>
                      <td>
                        <Badge tone={SEVERITY_TONE[zone.risk_level] ?? 'slate'}>
                          {zone.risk_level}
                        </Badge>
                      </td>
                      <td className="w-32">
                        <div className="flex items-center gap-2">
                          <Progress
                            value={zone.risk_score}
                            tone={zone.risk_score > 66 ? 'red' : zone.risk_score > 33 ? 'amber' : 'emerald'}
                            label={`Risk score for ${zone.zone_name}`}
                            className="flex-1"
                          />
                          <span className="mono w-8 shrink-0 text-right text-[0.6875rem] tabular-nums">
                            {Math.round(zone.risk_score)}
                          </span>
                        </div>
                      </td>
                      <td className="tabular-nums">{formatNumber(zone.total_requests)}</td>
                      <td className="tabular-nums">{formatNumber(zone.pending_requests)}</td>
                      <td className="tabular-nums">
                        {formatNumber(zone.population_affected, { compact: true })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          </Card>

          {zones.some((zone) => zone.explanation || zone.contributing_factors) ? (
            <Card className="overflow-hidden">
              <CardHeader title="Why these scores?" icon="info" />
              <ul className="divide-y divide-[var(--rn-border)]">
                {zones
                  .filter((zone) => zone.explanation || zone.contributing_factors)
                  .map((zone) => (
                    <li key={zone.zone_name} className="px-5 py-4">
                      <p className="text-[0.8125rem] font-medium text-[var(--rn-text)]">
                        {zone.zone_name}
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-[var(--rn-text-3)]">
                        {zone.explanation ??
                          (Array.isArray(zone.contributing_factors)
                            ? zone.contributing_factors.join(' · ')
                            : String(zone.contributing_factors))}
                      </p>
                    </li>
                  ))}
              </ul>
            </Card>
          ) : null}
        </>
      )}
    </div>
  );
}
