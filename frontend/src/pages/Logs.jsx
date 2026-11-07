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
  SkeletonTable,
  Table,
  TableWrap,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { formatDateTime } from '../lib/format';

const ACTION_TONES = {
  allocation: 'emerald',
  request_create: 'indigo',
  request_update: 'blue',
  stock_update: 'cyan',
  restock: 'emerald',
  alert: 'red',
  risk_update: 'amber',
  system: 'slate',
};

export function Logs() {
  useDocumentTitle('System Logs');
  const [search, setSearch] = useState('');

  const fetcher = useCallback(({ signal }) => api.logs({ signal }), []);
  const { data, error, loading, refresh } = useApi(fetcher);

  const rows = useMemo(() => {
    const all = data?.logs ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return all;
    return all.filter((row) =>
      [row.action_type, row.table_name, row.details, row.user]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(term)),
    );
  }, [data, search]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Tools"
        title="System Logs"
        description="Append-only audit trail of every write the platform has made."
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={refresh} loading={loading}>
            Refresh
          </Button>
        }
      />

      <Card className="overflow-hidden">
        <CardHeader
          title="Audit Trail"
          subtitle={`${rows.length} of ${data?.logs?.length ?? 0} entries`}
          icon="list"
          action={
            <div className="relative">
              <span
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rn-text-3)]"
                aria-hidden="true"
              >
                <Icon name="search" className="h-3.5 w-3.5" />
              </span>
              <label className="sr-only" htmlFor="log-search">
                Filter log entries
              </label>
              <Input
                id="log-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Filter…"
                className="h-8 w-44 pl-8 text-xs"
              />
            </div>
          }
        />

        {error ? (
          <ErrorState error={error} onRetry={refresh} />
        ) : loading ? (
          <SkeletonTable rows={10} columns={4} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={search ? 'search' : 'list'}
            title={search ? 'No matching entries' : 'No activity recorded'}
            description={
              search
                ? 'Try a different search term.'
                : 'Audit entries appear as requests are created and allocations dispatched.'
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
                  <th scope="col">Action</th>
                  <th scope="col">Table</th>
                  <th scope="col">Details</th>
                  <th scope="col">When</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Badge tone={ACTION_TONES[row.action_type] ?? 'slate'}>
                        {row.action_type}
                      </Badge>
                    </td>
                    <td className="mono text-[0.6875rem] text-[var(--rn-text-2)]">
                      {row.table_name}
                      {row.record_id ? `#${row.record_id}` : ''}
                    </td>
                    <td className="max-w-md truncate text-[var(--rn-text-2)]" title={row.details}>
                      {row.details || '—'}
                    </td>
                    <td className="whitespace-nowrap text-[var(--rn-text-3)]">
                      {formatDateTime(row.timestamp)}
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
