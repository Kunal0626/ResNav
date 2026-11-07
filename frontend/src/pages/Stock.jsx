import { useCallback, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  Progress,
  SkeletonTable,
  Table,
  TableWrap,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { formatNumber, formatRelative } from '../lib/format';

export function Stock() {
  useDocumentTitle('Live Stock');
  const [lowOnly, setLowOnly] = useState(false);
  const [search, setSearch] = useState('');

  const fetcher = useCallback(({ signal }) => api.stock({ lowOnly }, { signal }), [lowOnly]);
  const { data, error, loading, refresh } = useApi(fetcher, { deps: [lowOnly] });

  const rows = useMemo(() => {
    const all = data?.stock ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return all;
    return all.filter(
      (row) =>
        row.provider_name.toLowerCase().includes(term) ||
        row.resource_name.toLowerCase().includes(term),
    );
  }, [data, search]);

  const lowCount = (data?.stock ?? []).filter((row) => row.is_low).length;

  // Two different things, deliberately shown separately.
  //
  //   lowCount  is recomputed from the current quantity on every request:
  //             "how many lines are under threshold right now".
  //   alerts    is state the database raised the moment stock crossed the
  //             line and will resolve when it recovers, so it knows WHEN
  //             the shortage started. At most one open alert can exist per
  //             centre and resource.
  const alerts = data?.alerts ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="Live Stock"
        description="Current inventory across every relief centre, with safety thresholds and depletion warnings."
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={refresh} loading={loading}>
            Refresh
          </Button>
        }
      />

      {alerts.length > 0 ? (
        <Card className="overflow-hidden border-amber-500/30">
          <CardHeader
            title="Standing low-stock alerts"
            subtitle={
              `${alerts.length} open · raised by a database trigger the moment stock ` +
              `crossed its threshold, and resolved automatically when it recovers`
            }
          />
          <div className="divide-y divide-[var(--rn-line)]">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex flex-wrap items-center gap-3 px-4 py-3 text-xs sm:px-5"
              >
                <Icon name="alert" className="h-4 w-4 shrink-0 text-amber-500" />
                <div className="min-w-[12rem] flex-1">
                  <p className="font-medium text-[var(--rn-text)]">{alert.resource_name}</p>
                  <p className="text-[var(--rn-text-2)]">{alert.provider_name}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-[var(--rn-text)]">
                    {formatNumber(alert.quantity_now)}{' '}
                    <span className="text-[var(--rn-text-2)]">
                      / {formatNumber(alert.threshold_at_alert)} {alert.unit}
                    </span>
                  </p>
                  <p className="text-[var(--rn-text-2)]">
                    short by {formatNumber(alert.shortfall)}
                  </p>
                </div>
                <p className="w-full text-[var(--rn-text-2)] sm:w-auto sm:min-w-[11rem] sm:text-right">
                  raised {formatRelative(alert.raised_at)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {lowCount > 0 && !lowOnly ? (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4"
        >
          <Icon name="alert" className="h-4 w-4 shrink-0 text-amber-500" />
          <p className="flex-1 text-xs text-[var(--rn-text-2)]">
            <strong className="font-semibold text-[var(--rn-text)]">{lowCount}</strong> stock lines
            are below their safety threshold right now. This is counted from the current
            quantities, so it includes lines that opened low and never crossed the
            threshold — which is why it differs from the alert count above.
          </p>
          <Button variant="ghost" size="sm" onClick={() => setLowOnly(true)}>
            Show only these
          </Button>
        </div>
      ) : null}

      <Card className="overflow-hidden">
        <CardHeader
          title={lowOnly ? 'Low Stock Lines' : 'All Stock Lines'}
          subtitle={`${rows.length} of ${data?.stock?.length ?? 0} lines`}
          icon="box"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <span
                  className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rn-text-3)]"
                  aria-hidden="true"
                >
                  <Icon name="search" className="h-3.5 w-3.5" />
                </span>
                <label className="sr-only" htmlFor="stock-search">
                  Filter stock lines
                </label>
                <Input
                  id="stock-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Filter…"
                  className="h-8 w-40 pl-8 text-xs"
                />
              </div>
              <Button
                variant={lowOnly ? 'primary' : 'ghost'}
                size="sm"
                icon="filter"
                onClick={() => setLowOnly((value) => !value)}
                aria-pressed={lowOnly}
              >
                Low only
              </Button>
            </div>
          }
        />

        {error ? (
          <ErrorState error={error} onRetry={refresh} />
        ) : loading ? (
          <SkeletonTable rows={8} columns={5} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={search ? 'search' : lowOnly ? 'check' : 'box'}
            title={
              search
                ? 'No matching stock lines'
                : lowOnly
                  ? 'Nothing below threshold'
                  : 'No stock recorded'
            }
            description={
              search
                ? 'Try a different centre or resource name.'
                : lowOnly
                  ? 'Every resource line is above its configured safety level.'
                  : 'Stock levels appear here once providers are seeded with inventory.'
            }
            action={
              search || lowOnly ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearch('');
                    setLowOnly(false);
                  }}
                >
                  Clear filters
                </Button>
              ) : null
            }
          />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <th scope="col">Centre</th>
                  <th scope="col">Resource</th>
                  <th scope="col">On hand</th>
                  <th scope="col">Against threshold</th>
                  <th scope="col">Updated</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const ratio = row.threshold > 0 ? (row.quantity / row.threshold) * 100 : 100;
                  return (
                    <tr key={row.id}>
                      <td className="font-medium text-[var(--rn-text)]">{row.provider_name}</td>
                      <td>{row.resource_name}</td>
                      <td className="tabular-nums">
                        {formatNumber(row.quantity)}
                        <span className="ml-1 text-[0.6875rem] text-[var(--rn-text-3)]">
                          {row.unit}
                        </span>
                      </td>
                      <td className="w-48">
                        <div className="flex items-center gap-2">
                          <Progress
                            value={Math.min(ratio, 100)}
                            tone={row.is_low ? 'red' : ratio < 150 ? 'amber' : 'emerald'}
                            label={`${row.resource_name} at ${row.provider_name}`}
                            className="flex-1"
                          />
                          {row.is_low ? (
                            <Badge tone="red">Low</Badge>
                          ) : (
                            <span className="mono w-12 shrink-0 text-right text-[0.6875rem] tabular-nums text-[var(--rn-text-3)]">
                              {formatNumber(row.threshold)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="whitespace-nowrap text-[var(--rn-text-3)]">
                        {formatRelative(row.updated_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}
