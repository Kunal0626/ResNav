import { useCallback, useMemo, useState } from 'react';
import { Chart, PALETTE } from '../components/charts/Chart';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  PageHeader,
  SkeletonTable,
  Table,
  TableWrap,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { STATUS_TONE } from '../lib/constants';
import { formatDateTime, formatNumber, titleCase } from '../lib/format';

/** Column definitions per table, so one renderer covers all five datasets. */
const TABLES = {
  providers: {
    label: 'Providers',
    icon: 'location',
    searchKeys: ['name', 'city', 'state'],
    columns: [
      { key: 'name', label: 'Name', bold: true },
      { key: 'city', label: 'City' },
      { key: 'state', label: 'State' },
      { key: 'total_stock', label: 'Total stock', numeric: true },
      { key: 'phone', label: 'Phone', mono: true },
    ],
  },
  resources: {
    label: 'Resources',
    icon: 'box',
    searchKeys: ['name', 'category'],
    columns: [
      { key: 'name', label: 'Name', bold: true },
      { key: 'category', label: 'Category' },
      { key: 'unit', label: 'Unit' },
    ],
  },
  stock: {
    label: 'Stock',
    icon: 'database',
    searchKeys: ['provider_name', 'resource_name'],
    columns: [
      { key: 'provider_name', label: 'Centre', bold: true },
      { key: 'resource_name', label: 'Resource' },
      { key: 'quantity', label: 'Quantity', numeric: true },
      { key: 'threshold', label: 'Threshold', numeric: true },
      { key: 'is_low', label: 'Status', render: (row) => (row.is_low ? <Badge tone="red">Low</Badge> : <Badge tone="emerald">OK</Badge>) },
    ],
  },
  requests: {
    label: 'Requests',
    icon: 'clipboard',
    searchKeys: ['zone', 'resource', 'status'],
    columns: [
      { key: 'zone', label: 'Zone', bold: true },
      { key: 'resource', label: 'Resource' },
      { key: 'quantity_requested', label: 'Requested', numeric: true },
      { key: 'status', label: 'Status', render: (row) => <Badge tone={STATUS_TONE[row.status] ?? 'slate'}>{titleCase(row.status)}</Badge> },
      { key: 'created_at', label: 'Created', render: (row) => formatDateTime(row.created_at) },
    ],
  },
  allocations: {
    label: 'Allocations',
    icon: 'truck',
    searchKeys: ['provider_name', 'resource_name', 'zone'],
    columns: [
      { key: 'provider_name', label: 'Centre', bold: true },
      { key: 'resource_name', label: 'Resource' },
      { key: 'quantity', label: 'Quantity', numeric: true },
      { key: 'zone', label: 'Zone' },
      { key: 'allocated_at', label: 'Dispatched', render: (row) => formatDateTime(row.allocated_at) },
    ],
  },
};

export function Explorer() {
  useDocumentTitle('Data Explorer');
  const [active, setActive] = useState('providers');
  const [search, setSearch] = useState('');

  const fetcher = useCallback(({ signal }) => api.explorer({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  const config = TABLES[active];
  const rows = useMemo(() => {
    const all = data?.[active] ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return all;
    return all.filter((row) =>
      config.searchKeys.some((key) => String(row[key] ?? '').toLowerCase().includes(term)),
    );
  }, [data, active, search, config]);

  const stockChart = useMemo(() => {
    const chart = data?.charts?.stock_by_resource;
    if (!chart?.labels?.length) return null;
    return {
      labels: chart.labels,
      datasets: [
        {
          label: 'Units in stock',
          data: chart.values,
          backgroundColor: PALETTE[0],
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    };
  }, [data]);

  const statusChart = useMemo(() => {
    const chart = data?.charts?.requests_by_status;
    if (!chart?.labels?.length) return null;
    return {
      labels: chart.labels,
      datasets: [
        {
          data: chart.values,
          backgroundColor: PALETTE,
          borderWidth: 0,
        },
      ],
    };
  }, [data]);

  const exportCsv = () => {
    const header = config.columns.map((column) => column.label).join(',');
    const body = rows
      .map((row) =>
        config.columns
          .map((column) => {
            const value = row[column.key];
            const text = value == null ? '' : String(value);
            // Quote anything containing a delimiter or quote.
            return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
          })
          .join(','),
      )
      .join('\n');

    const blob = new Blob([`${header}\n${body}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `resnav-${active}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Tools"
        title="Data Explorer"
        description="Read-only view over the core tables, with aggregate charts and CSV export."
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
      ) : (
        <>
          {!loading && (stockChart || statusChart) ? (
            <div className="grid gap-6 lg:grid-cols-3">
              {stockChart ? (
                <Card className="overflow-hidden lg:col-span-2">
                  <CardHeader title="Stock by Resource" icon="chart" />
                  <div className="p-5">
                    <Chart
                      type="bar"
                      data={stockChart}
                      height={260}
                      ariaLabel="Bar chart of total units in stock per resource"
                    />
                  </div>
                </Card>
              ) : null}

              {statusChart ? (
                <Card className="overflow-hidden">
                  <CardHeader title="Requests by Status" icon="clipboard" />
                  <div className="p-5">
                    <Chart
                      type="doughnut"
                      data={statusChart}
                      height={260}
                      ariaLabel="Doughnut chart of request counts by status"
                      options={{ plugins: { legend: { display: true, position: 'bottom' } }, cutout: '62%' }}
                    />
                  </div>
                </Card>
              ) : null}
            </div>
          ) : null}

          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rn-border)] px-5 py-3">
              <div
                className="flex flex-wrap gap-1"
                role="tablist"
                aria-label="Select a table to browse"
              >
                {Object.entries(TABLES).map(([key, table]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={active === key}
                    onClick={() => {
                      setActive(key);
                      setSearch('');
                    }}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      active === key
                        ? 'bg-indigo-500/10 text-indigo-500'
                        : 'text-[var(--rn-text-2)] hover:bg-[var(--rn-border)]/60'
                    }`}
                  >
                    <Icon name={table.icon} className="h-3.5 w-3.5" />
                    {table.label}
                    <span className="tabular-nums opacity-60">{data?.[key]?.length ?? 0}</span>
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <div className="relative">
                  <span
                    className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rn-text-3)]"
                    aria-hidden="true"
                  >
                    <Icon name="search" className="h-3.5 w-3.5" />
                  </span>
                  <label className="sr-only" htmlFor="explorer-search">
                    Filter rows
                  </label>
                  <Input
                    id="explorer-search"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Filter…"
                    className="h-8 w-40 pl-8 text-xs"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon="download"
                  onClick={exportCsv}
                  disabled={!rows.length}
                >
                  CSV
                </Button>
              </div>
            </div>

            {loading ? (
              <SkeletonTable rows={8} columns={config.columns.length} />
            ) : rows.length === 0 ? (
              <EmptyState
                icon={search ? 'search' : config.icon}
                title={search ? 'No matching rows' : `No ${config.label.toLowerCase()} yet`}
                description={
                  search
                    ? 'Try a different search term.'
                    : 'This table is empty. Seed the database or create records to populate it.'
                }
                action={
                  search ? (
                    <Button variant="ghost" size="sm" onClick={() => setSearch('')}>
                      Clear filter
                    </Button>
                  ) : null
                }
              />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      {config.columns.map((column) => (
                        <th key={column.key} scope="col">
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={row.id ?? index}>
                        {config.columns.map((column) => (
                          <td
                            key={column.key}
                            className={[
                              column.bold && 'font-medium text-[var(--rn-text)]',
                              column.numeric && 'tabular-nums',
                              column.mono && 'mono text-[0.6875rem]',
                            ]
                              .filter(Boolean)
                              .join(' ')}
                          >
                            {column.render
                              ? column.render(row)
                              : column.numeric
                                ? formatNumber(row[column.key])
                                : (row[column.key] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
