import { useCallback } from 'react';
import { InsightList } from '../components/InsightList';
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
import { formatDays, formatNumber } from '../lib/format';

export function CommandCenter() {
  useDocumentTitle('AI Command Center');
  const fetcher = useCallback(({ signal }) => api.dashboard({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Command Center"
        description="Consolidated view of depletion forecasts, zone risk scores, detected anomalies and the insights derived from them."
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
        <div className="grid gap-6 lg:grid-cols-2">
          <SkeletonCard rows={4} />
          <SkeletonCard rows={4} />
          <SkeletonCard rows={4} />
          <SkeletonCard rows={4} />
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="overflow-hidden lg:col-span-2">
            <CardHeader
              title="Generated Insights"
              subtitle="Synthesised from the four analyses below"
              icon="bulb"
            />
            <InsightList insights={data?.insights ?? []} />
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="Zone Risk"
              subtitle="Weighted by demand, severity and unmet supply"
              icon="shield"
            />
            {data?.zone_risks?.length ? (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th scope="col">Zone</th>
                      <th scope="col">Level</th>
                      <th scope="col">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.zone_risks.map((zone) => (
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
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            ) : (
              <EmptyState
                icon="shield"
                title="No zones scored"
                description="Zone risk is computed from request volume and unmet demand. Add zones and requests to populate this panel."
              />
            )}
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="Depletion Forecast"
              subtitle="Highest-risk resource lines"
              icon="chart"
              action={
                <Button variant="ghost" size="sm" to="/forecast" icon="external" iconPosition="right">
                  Full view
                </Button>
              }
            />
            {data?.forecasts?.length ? (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th scope="col">Resource</th>
                      <th scope="col">Stock</th>
                      <th scope="col">Runway</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.forecasts.map((row, index) => (
                      <tr key={`${row.resource}-${index}`}>
                        <td className="font-medium text-[var(--rn-text)]">{row.resource}</td>
                        <td className="tabular-nums">{formatNumber(row.current_stock)}</td>
                        <td>
                          <Badge
                            tone={
                              typeof row.days_until_depletion === 'number'
                                ? row.days_until_depletion < 7
                                  ? 'red'
                                  : row.days_until_depletion < 21
                                    ? 'amber'
                                    : 'emerald'
                                : 'emerald'
                            }
                          >
                            {typeof row.days_until_depletion === 'number'
                              ? formatDays(row.days_until_depletion)
                              : row.days_until_depletion}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            ) : (
              <EmptyState
                icon="chart"
                title="Not enough history"
                description="Depletion forecasts need at least two recorded stock movements per resource line."
              />
            )}
          </Card>

          <Card className="overflow-hidden lg:col-span-2">
            <CardHeader
              title="Detected Anomalies"
              subtitle="Isolation Forest and threshold detectors over provider performance and stock movement"
              icon="alert"
            />
            {data?.anomalies?.length ? (
              <ul className="divide-y divide-[var(--rn-border)]">
                {data.anomalies.map((anomaly, index) => (
                  <li key={index} className="flex items-start gap-3 px-5 py-4">
                    <Badge tone={SEVERITY_TONE[anomaly.severity] ?? 'amber'} className="mt-0.5 shrink-0">
                      {anomaly.severity ?? 'medium'}
                    </Badge>
                    <div className="min-w-0">
                      <p className="text-[0.8125rem] text-[var(--rn-text)]">
                        {anomaly.message ?? anomaly.description ?? anomaly.type}
                      </p>
                      {anomaly.explanation ? (
                        <p className="mt-1 text-xs text-[var(--rn-text-3)]">{anomaly.explanation}</p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon="check"
                title="No anomalies detected"
                description="Provider performance and stock movement are all within expected ranges."
              />
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
