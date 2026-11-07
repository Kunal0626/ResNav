import { useCallback, useMemo } from 'react';
import { Chart, PALETTE } from '../components/charts/Chart';
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

export function Forecast() {
  useDocumentTitle('AI Forecast');
  const fetcher = useCallback(({ signal }) => api.forecast({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  const seriesFetcher = useCallback(({ signal }) => api.forecastSeries({ signal }), []);
  const { data: series } = useApi(seriesFetcher);

  const chartData = useMemo(() => {
    const history = series?.history ?? series?.actual ?? [];
    const projection = series?.forecast ?? series?.predicted ?? [];
    if (!history.length && !projection.length) return null;

    const labels = [
      ...history.map((point) => point.time?.slice(0, 10) ?? point.date ?? ''),
      ...projection.map((point) => point.time?.slice(0, 10) ?? point.date ?? ''),
    ];

    return {
      labels,
      datasets: [
        {
          label: 'Recorded stock',
          data: [...history.map((p) => p.qty ?? p.value), ...Array(projection.length).fill(null)],
          borderColor: PALETTE[0],
          backgroundColor: 'rgba(99,102,241,0.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: 'Projected',
          data: [
            ...Array(Math.max(0, history.length - 1)).fill(null),
            history.length ? (history[history.length - 1].qty ?? history[history.length - 1].value) : null,
            ...projection.map((p) => p.qty ?? p.value),
          ],
          borderColor: PALETTE[1],
          borderDash: [5, 4],
          fill: false,
          tension: 0.35,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    };
  }, [series]);

  const rows = data?.forecast ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Depletion Forecast"
        description="Burn rates and days of cover per resource line, computed from recorded stock movements."
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
          <SkeletonCard rows={6} />
        </>
      ) : !data?.sufficient_history ? (
        <Card>
          <EmptyState
            icon="chart"
            title="Not enough stock history to forecast"
            description="Depletion projections need at least two recorded movements for a resource line. Allocate some requests, then check back."
            action={
              <Button variant="primary" size="sm" to="/requests" icon="clipboard">
                Go to requests
              </Button>
            }
          />
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <SummaryTile
              label="Peak risk index"
              value={data.peak_risk_index ?? data.avg_risk_index}
              suffix="/ 100"
              tone={
                (data.peak_risk_index ?? 0) > 66
                  ? 'red'
                  : (data.peak_risk_index ?? 0) > 33
                    ? 'amber'
                    : 'emerald'
              }
            />
            <SummaryTile
              label="Nearest depletion"
              value={data.nearest_depletion == null ? '—' : formatDays(data.nearest_depletion)}
              tone={data.nearest_depletion != null && data.nearest_depletion < 7 ? 'red' : 'indigo'}
            />
            <SummaryTile
              label="Critical lines"
              value={`${data.critical_lines ?? 0} of ${rows.length}`}
              tone={data.critical_lines > 0 ? 'red' : 'indigo'}
            />
          </div>

          <Card className="overflow-hidden">
            <CardHeader title="AI Summary" icon="bulb" />
            <div className="p-5">
              <p className="ai-reasoning-box text-[0.8125rem] leading-relaxed">{data.ai_summary}</p>
            </div>
          </Card>

          {chartData ? (
            <Card className="overflow-hidden">
              <CardHeader
                title="Aggregate Stock Trend"
                subtitle="Total units recorded per day, with a projected continuation"
                icon="trend"
              />
              <div className="p-5">
                <Chart
                  type="line"
                  data={chartData}
                  height={300}
                  ariaLabel="Line chart of total stock over time with a projection"
                  options={{ plugins: { legend: { display: true, position: 'bottom' } } }}
                />
              </div>
            </Card>
          ) : null}

          <Card className="overflow-hidden">
            <CardHeader
              title="Resource Lines"
              subtitle={`${rows.length} provider–resource combinations, highest risk first`}
              icon="box"
            />
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th scope="col">Centre</th>
                    <th scope="col">Resource</th>
                    <th scope="col">Stock</th>
                    <th scope="col">Daily burn</th>
                    <th scope="col">Runway</th>
                    <th scope="col">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={`${row.provider}-${row.resource}-${index}`}>
                      <td className="font-medium text-[var(--rn-text)]">{row.provider}</td>
                      <td>{row.resource}</td>
                      <td className="tabular-nums">{formatNumber(row.current_stock)}</td>
                      <td className="mono tabular-nums text-[var(--rn-text-3)]">
                        {row.daily_rate > 0 ? `${row.daily_rate}/day` : '—'}
                      </td>
                      <td>
                        <Badge tone={SEVERITY_TONE[row.status] ?? 'slate'}>
                          {typeof row.days_left === 'number' ? formatDays(row.days_left) : row.days_left}
                        </Badge>
                      </td>
                      <td className="w-28">
                        <div className="flex items-center gap-2">
                          <Progress
                            value={row.risk_score}
                            tone={row.risk_score > 66 ? 'red' : row.risk_score > 33 ? 'amber' : 'emerald'}
                            label={`Risk for ${row.resource} at ${row.provider}`}
                            className="flex-1"
                          />
                          <span className="mono w-7 shrink-0 text-right text-[0.6875rem] tabular-nums">
                            {row.risk_score}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          </Card>
        </>
      )}
    </div>
  );
}

function SummaryTile({ label, value, suffix, tone = 'indigo' }) {
  const tones = {
    indigo: 'text-indigo-500',
    emerald: 'text-emerald-500',
    amber: 'text-amber-500',
    red: 'text-red-500',
  };
  return (
    <div className="dash-card p-5">
      <p className="kpi-label">{label}</p>
      <p className={`mt-1.5 text-2xl font-bold tabular-nums ${tones[tone]}`}>
        {typeof value === 'number' ? formatNumber(value) : value}
        {suffix ? (
          <span className="ml-1 text-sm font-medium text-[var(--rn-text-3)]">{suffix}</span>
        ) : null}
      </p>
    </div>
  );
}
