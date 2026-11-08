import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DemoExamples } from '../components/DemoExamples';
import { KpiCard } from '../components/KpiCard';
import { InsightList } from '../components/InsightList';
import { RiskMap } from '../components/RiskMap';
import { Ticker } from '../components/Ticker';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  Table,
  TableWrap,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useGeolocation } from '../hooks/useGeolocation';
import { api } from '../lib/api';
import { STATUS_TONE } from '../lib/constants';
import { formatNumber, formatRelative, titleCase } from '../lib/format';

const KPIS = [
  { key: 'total_providers', label: 'Relief Centres', icon: 'location', tone: 'indigo', contextKey: 'providers' },
  { key: 'total_stock', label: 'Units In Stock', icon: 'box', tone: 'emerald', contextKey: 'stock', series: 'stock' },
  { key: 'active_requests', label: 'Active Requests', icon: 'clipboard', tone: 'violet', contextKey: 'requests' },
  { key: 'pending_allocations', label: 'Awaiting Dispatch', icon: 'clock', tone: 'amber', contextKey: 'pending' },
  { key: 'low_stock_alerts', label: 'Low Stock Alerts', icon: 'alert', tone: 'red', contextKey: 'low_stock' },
];

export function Home() {
  useDocumentTitle('Overview');
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const { coords, fallback, denied, locate, loading: locating } = useGeolocation();

  const fetchOverview = useCallback(({ signal }) => api.overview({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetchOverview);

  // Takes the text directly, so the form and the demo's example chips share
  // one path to the results page.
  const go = useCallback(
    (text) => {
      const trimmed = String(text ?? '').trim();
      if (!trimmed) return;
      navigate('/results', { state: { query: trimmed, coords, fallback } });
    },
    [navigate, coords, fallback],
  );

  const onSubmit = (event) => {
    event.preventDefault();
    go(query);
  };

  return (
    <div className="space-y-6">
      <SearchHero
        query={query}
        onQueryChange={setQuery}
        onSubmit={onSubmit}
        fallback={fallback}
        denied={denied}
        locating={locating}
        onLocate={locate}
        onPickExample={go}
      />

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={refresh} title="Could not load the overview" />
        </Card>
      ) : null}

      {data?.demo_mode ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
        >
          <Icon name="info" className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <p className="text-xs leading-relaxed text-[var(--rn-text-2)]">
            <strong className="font-semibold text-[var(--rn-text)]">Sample data.</strong> The
            database has no providers yet, so the figures below are illustrative. Run{' '}
            <code className="mono rounded bg-[var(--rn-border)] px-1 py-0.5">
              python manage.py seed
            </code>{' '}
            in the backend to load real data.
          </p>
        </div>
      ) : null}

      <section aria-label="Key metrics" className="kpi-grid">
        {KPIS.map((kpi) => (
          <KpiCard
            key={kpi.key}
            label={kpi.label}
            icon={kpi.icon}
            tone={kpi.tone}
            loading={loading}
            value={data?.stats?.[kpi.key] ?? 0}
            context={data?.kpi_context?.[kpi.contextKey]}
            series={kpi.series ? data?.sparklines?.[kpi.series] : undefined}
          />
        ))}
      </section>

      {data?.ticker?.length ? <Ticker messages={data.ticker} /> : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="overflow-hidden xl:col-span-2">
          <CardHeader
            title="Relief Network"
            subtitle="Centres and zone risk intensity across the operating area"
            icon="globe"
          />
          {loading ? (
            <div className="p-5">
              <div className="skeleton h-[340px] w-full rounded-xl" />
            </div>
          ) : (
            <div className="p-5">
              <RiskMap providers={data?.providers ?? []} heatmap={data?.heatmap ?? []} />
            </div>
          )}
        </Card>

        <Card className="overflow-hidden">
          <CardHeader title="AI Insights" subtitle="Derived from current operational data" icon="bulb" />
          {loading ? (
            <div className="space-y-3 p-5">
              {[0, 1, 2].map((index) => (
                <div key={index} className="skeleton h-12 w-full" />
              ))}
            </div>
          ) : (
            <InsightList insights={data?.insights ?? []} />
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ActivityCard
          title="Recent Allocations"
          icon="truck"
          loading={loading}
          rows={data?.recent_allocations ?? []}
          emptyTitle="No allocations yet"
          emptyDescription="Dispatched resources will appear here once requests are allocated."
          columns={['Zone', 'Resource', 'Quantity', 'When']}
          renderRow={(row) => (
            <>
              <td className="font-medium text-[var(--rn-text)]">{row.zone}</td>
              <td>{row.resource}</td>
              <td className="tabular-nums">{formatNumber(row.quantity)}</td>
              <td className="whitespace-nowrap text-[var(--rn-text-3)]">
                {formatRelative(row.time)}
              </td>
            </>
          )}
        />

        <ActivityCard
          title="Recent Requests"
          icon="clipboard"
          loading={loading}
          rows={data?.recent_requests ?? []}
          emptyTitle="No requests yet"
          emptyDescription="Incoming resource requests from zones will be listed here."
          action={
            <Button variant="ghost" size="sm" to="/requests" icon="external" iconPosition="right">
              Manage
            </Button>
          }
          columns={['Zone', 'Resource', 'Quantity', 'Status']}
          renderRow={(row) => (
            <>
              <td className="font-medium text-[var(--rn-text)]">{row.zone}</td>
              <td>{row.resource}</td>
              <td className="tabular-nums">{formatNumber(row.quantity)}</td>
              <td>
                <Badge tone={STATUS_TONE[row.status] ?? 'slate'}>{titleCase(row.status)}</Badge>
              </td>
            </>
          )}
        />
      </div>
    </div>
  );
}

function SearchHero({
  query,
  onQueryChange,
  onSubmit,
  fallback,
  denied,
  locating,
  onLocate,
  onPickExample,
}) {
  return (
    <Card className="page-hero overflow-hidden">
      <div className="p-6 sm:p-8">
        <p className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-[0.12em] text-indigo-500 dark:text-indigo-400">
          Semantic Resource Search
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--rn-text)] sm:text-3xl">
          What do you need, and where?
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--rn-text-2)]">
          Describe the need in plain language. ResNav classifies intent, extracts quantity and
          urgency, then ranks nearby centres by semantic match, stock on hand and distance.
        </p>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <span
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--rn-text-3)]"
              aria-hidden="true"
            >
              <Icon name="search" className="h-4 w-4" />
            </span>
            <label className="sr-only" htmlFor="home-search">
              Describe what you need
            </label>
            <Input
              id="home-search"
              value={query}
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="e.g. we urgently need 500 water packets for a flooded village"
              className="pl-10"
              autoComplete="off"
              maxLength={500}
            />
          </div>
          <Button type="submit" variant="ai" icon="search" disabled={!query.trim()}>
            Search
          </Button>
        </form>

        <DemoExamples onPick={onPickExample} className="mt-5" />

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.6875rem] text-[var(--rn-text-3)]">
          {locating ? (
            <span>Locating…</span>
          ) : fallback ? (
            <span className="inline-flex items-center gap-1.5">
              <Icon name="location" className="h-3 w-3" />
              {denied
                ? 'Location access denied — ranking from Delhi.'
                : 'Using Delhi as the default origin.'}
              <button
                type="button"
                onClick={onLocate}
                className="font-semibold text-indigo-500 underline-offset-2 hover:underline"
              >
                Use my location
              </button>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-500">
              <Icon name="check" className="h-3 w-3" />
              Ranking from your current location.
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}

function ActivityCard({
  title,
  icon,
  rows,
  columns,
  renderRow,
  loading,
  emptyTitle,
  emptyDescription,
  action,
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title={title} icon={icon} action={action} />
      {loading ? (
        <div className="space-y-2.5 p-5">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="skeleton h-4 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon="inbox" title={emptyTitle} description={emptyDescription} />
      ) : (
        <TableWrap>
          <Table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.id ?? index}>{renderRow(row)}</tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      )}
    </Card>
  );
}
