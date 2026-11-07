import { useCallback } from 'react';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonTable,
  Table,
  TableWrap,
} from '../components/ui';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { STATUS_TONE } from '../lib/constants';
import { formatDateTime, formatNumber, titleCase } from '../lib/format';

export function Allocations() {
  useDocumentTitle('Allocation History');
  const fetcher = useCallback(({ signal }) => api.allocations({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  const rows = data?.allocations ?? [];
  const totalUnits = rows.reduce((sum, row) => sum + Number(row.quantity || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="Allocation History"
        description="Every dispatch recorded against a request, with the centre that supplied it."
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={refresh} loading={loading}>
            Refresh
          </Button>
        }
      />

      {!loading && !error && rows.length ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Tile label="Allocations" value={formatNumber(rows.length)} />
          <Tile label="Units dispatched" value={formatNumber(totalUnits, { compact: true })} />
          <Tile
            label="Centres involved"
            value={formatNumber(new Set(rows.map((row) => row.provider_id)).size)}
          />
        </div>
      ) : null}

      <Card className="overflow-hidden">
        <CardHeader title="Dispatch Log" subtitle="Most recent first" icon="truck" />

        {error ? (
          <ErrorState error={error} onRetry={refresh} />
        ) : loading ? (
          <SkeletonTable rows={8} columns={6} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon="truck"
            title="Nothing dispatched yet"
            description="Allocate a pending request and the dispatch record will appear here."
            action={
              <Button variant="primary" size="sm" to="/requests" icon="clipboard">
                Go to requests
              </Button>
            }
          />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <th scope="col">Zone</th>
                  <th scope="col">Resource</th>
                  <th scope="col">Quantity</th>
                  <th scope="col">Supplied by</th>
                  <th scope="col">Request</th>
                  <th scope="col">When</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="font-medium text-[var(--rn-text)]">{row.zone}</td>
                    <td>{row.resource_name}</td>
                    <td className="tabular-nums">
                      {formatNumber(row.quantity)}
                      <span className="ml-1 text-[0.6875rem] text-[var(--rn-text-3)]">
                        {row.unit}
                      </span>
                    </td>
                    <td>{row.provider_name}</td>
                    <td>
                      <Badge tone={STATUS_TONE[row.request_status] ?? 'slate'}>
                        #{row.request_id} · {titleCase(row.request_status)}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap text-[var(--rn-text-3)]">
                      {formatDateTime(row.allocated_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <div className="dash-card p-5">
      <p className="kpi-label">{label}</p>
      <p className="mt-1.5 text-2xl font-bold tabular-nums text-[var(--rn-text)]">{value}</p>
    </div>
  );
}
