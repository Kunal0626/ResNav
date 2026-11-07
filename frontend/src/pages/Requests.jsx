import { useCallback, useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  Portal,
  Select,
  SkeletonTable,
  Table,
  TableWrap,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useToast } from '../contexts/ToastContext';
import { useAction, useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { STATUS_TONE } from '../lib/constants';
import { formatNumber, formatRelative, titleCase } from '../lib/format';

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'allocated', label: 'Allocated' },
  { value: 'fulfilled', label: 'Fulfilled' },
  { value: 'rejected', label: 'Rejected' },
];

const EMPTY_FORM = {
  zone_id: '',
  resource_id: '',
  quantity_requested: '',
  severity: '1.5',
  urgency: '1.5',
  population_affected: '',
};

export function Requests() {
  useDocumentTitle('Resource Requests');
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [planFor, setPlanFor] = useState(null);

  const referenceFetcher = useCallback(({ signal }) => api.reference({ signal }), []);
  const { data: reference } = useApi(referenceFetcher);

  const requestsFetcher = useCallback(
    ({ signal }) => api.requests({ status: status || undefined }, { signal }),
    [status],
  );
  const { data, error, loading, refresh } = useApi(requestsFetcher, { deps: [status] });

  const requests = data?.requests ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="Resource Requests"
        description="Raise requests from disaster zones, review the AI allocation plan, and dispatch stock from the recommended centres."
        actions={
          <Button variant="ghost" size="sm" icon="refresh" onClick={refresh} loading={loading}>
            Refresh
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-3">
        <NewRequestForm reference={reference} onCreated={refresh} />

        <Card className="overflow-hidden xl:col-span-2">
          <CardHeader
            title="Request Queue"
            subtitle={`Sorted by priority score${requests.length ? ` · ${requests.length} shown` : ''}`}
            icon="clipboard"
            action={
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by status">
                {STATUS_FILTERS.map((option) => (
                  <button
                    key={option.value || 'all'}
                    type="button"
                    onClick={() => setStatus(option.value)}
                    aria-pressed={status === option.value}
                    className={`rounded-full px-2.5 py-1 text-[0.6875rem] font-semibold transition-colors ${
                      status === option.value
                        ? 'bg-indigo-500 text-white'
                        : 'bg-[var(--rn-border)]/60 text-[var(--rn-text-2)] hover:bg-[var(--rn-border)]'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            }
          />

          {error ? (
            <ErrorState error={error} onRetry={refresh} />
          ) : loading ? (
            <SkeletonTable rows={6} columns={5} />
          ) : requests.length === 0 ? (
            <EmptyState
              icon="inbox"
              title={status ? `No ${status} requests` : 'No requests yet'}
              description={
                status
                  ? 'Try a different status filter.'
                  : 'Create the first request using the form alongside.'
              }
            />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th scope="col">Zone</th>
                    <th scope="col">Resource</th>
                    <th scope="col">Requested</th>
                    <th scope="col">Priority</th>
                    <th scope="col">Status</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((request) => {
                    const outstanding = request.quantity_requested - request.quantity_allocated;
                    return (
                      <tr key={request.id}>
                        <td className="font-medium text-[var(--rn-text)]">{request.zone}</td>
                        <td>{request.resource}</td>
                        <td className="tabular-nums">
                          {formatNumber(request.quantity_requested)}
                          {request.quantity_allocated > 0 ? (
                            <span className="ml-1 text-[0.6875rem] text-[var(--rn-text-3)]">
                              ({formatNumber(request.quantity_allocated)} allocated)
                            </span>
                          ) : null}
                        </td>
                        <td className="mono tabular-nums text-[var(--rn-text-3)]">
                          {Number(request.priority_score ?? 0).toFixed(2)}
                        </td>
                        <td>
                          <Badge tone={STATUS_TONE[request.status] ?? 'slate'}>
                            {titleCase(request.status)}
                          </Badge>
                        </td>
                        <td className="text-right">
                          {outstanding > 0.001 ? (
                            <Button
                              variant="primary"
                              size="sm"
                              icon="bulb"
                              onClick={() => setPlanFor(request)}
                            >
                              Plan
                            </Button>
                          ) : (
                            <span className="text-[0.6875rem] text-[var(--rn-text-3)]">
                              {formatRelative(request.created_at)}
                            </span>
                          )}
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

      {planFor ? (
        <AllocationDialog
          request={planFor}
          onClose={() => setPlanFor(null)}
          onAllocated={() => {
            setPlanFor(null);
            refresh();
            toast.success('Allocation dispatched and stock deducted.');
          }}
        />
      ) : null}
    </div>
  );
}

function NewRequestForm({ reference, onCreated }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState({});

  const create = useAction(useCallback((payload) => api.createRequest(payload), []));

  const validate = () => {
    const next = {};
    if (!form.zone_id) next.zone_id = 'Select a zone.';
    if (!form.resource_id) next.resource_id = 'Select a resource.';

    const quantity = Number(form.quantity_requested);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      next.quantity_requested = 'Enter a quantity greater than zero.';
    }
    const population = Number(form.population_affected || 0);
    if (!Number.isFinite(population) || population < 0) {
      next.population_affected = 'Population cannot be negative.';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    if (!validate()) return;

    try {
      await create.execute({
        zone_id: Number(form.zone_id),
        resource_id: Number(form.resource_id),
        quantity_requested: Number(form.quantity_requested),
        severity: Number(form.severity),
        urgency: Number(form.urgency),
        population_affected: Number(form.population_affected || 0),
      });
      setForm(EMPTY_FORM);
      setErrors({});
      toast.success('Request created and queued by priority.');
      onCreated();
    } catch (caught) {
      // Field-level messages come back in `details.field` from the API.
      if (caught.details?.field) setErrors({ [caught.details.field]: caught.message });
      else toast.error(caught.message);
    }
  };

  return (
    <Card className="overflow-hidden xl:sticky xl:top-20 xl:self-start">
      <CardHeader title="New Request" icon="plus" />
      <CardBody>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Field label="Zone" htmlFor="zone" required error={errors.zone_id}>
            <Select
              id="zone"
              value={form.zone_id}
              onChange={(event) => setForm({ ...form, zone_id: event.target.value })}
            >
              <option value="">Select a zone</option>
              {(reference?.zones ?? []).map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Resource" htmlFor="request-resource" required error={errors.resource_id}>
            <Select
              id="request-resource"
              value={form.resource_id}
              onChange={(event) => setForm({ ...form, resource_id: event.target.value })}
            >
              <option value="">Select a resource</option>
              {(reference?.resources ?? []).map((resource) => (
                <option key={resource.id} value={resource.id}>
                  {/* Several seeded names already end in their unit, e.g.
                      "Food (kg)" — appending it again reads as "Food (kg) (kg)". */}
                  {resource.name.toLowerCase().includes(resource.unit.toLowerCase())
                    ? resource.name
                    : `${resource.name} (${resource.unit})`}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Quantity"
            htmlFor="request-quantity"
            required
            error={errors.quantity_requested}
          >
            <Input
              id="request-quantity"
              type="number"
              min="1"
              step="1"
              value={form.quantity_requested}
              invalid={Boolean(errors.quantity_requested)}
              onChange={(event) => setForm({ ...form, quantity_requested: event.target.value })}
              placeholder="e.g. 250"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Severity" htmlFor="severity">
              <Select
                id="severity"
                value={form.severity}
                onChange={(event) => setForm({ ...form, severity: event.target.value })}
              >
                <option value="1">Low</option>
                <option value="1.5">Moderate</option>
                <option value="2">High</option>
                <option value="3">Critical</option>
              </Select>
            </Field>

            <Field label="Urgency" htmlFor="request-urgency">
              <Select
                id="request-urgency"
                value={form.urgency}
                onChange={(event) => setForm({ ...form, urgency: event.target.value })}
              >
                <option value="1">Routine</option>
                <option value="1.5">Elevated</option>
                <option value="2">Urgent</option>
                <option value="3">Immediate</option>
              </Select>
            </Field>
          </div>

          <Field
            label="Population affected"
            htmlFor="population-affected"
            error={errors.population_affected}
            hint="Feeds the priority score."
          >
            <Input
              id="population-affected"
              type="number"
              min="0"
              step="100"
              value={form.population_affected}
              invalid={Boolean(errors.population_affected)}
              onChange={(event) => setForm({ ...form, population_affected: event.target.value })}
              placeholder="e.g. 5000"
            />
          </Field>

          <Button type="submit" variant="primary" icon="plus" className="w-full" loading={create.pending}>
            Create request
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function AllocationDialog({ request, onClose, onAllocated }) {
  const toast = useToast();
  const fetcher = useCallback(({ signal }) => api.recommendation(request.id, { signal }), [request.id]);
  const { data: plan, error, loading } = useApi(fetcher);

  const allocate = useAction(useCallback(() => api.allocate(request.id), [request.id]));

  const commit = async () => {
    try {
      await allocate.execute();
      onAllocated();
    } catch (caught) {
      toast.error(caught.message);
    }
  };

  // Escape closes the dialog, and body scroll is locked while it is open.
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <Portal>
    <div
      className="ai-modal-overlay fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="allocation-title"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="ai-modal-box max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-t-2xl sm:rounded-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rn-border)] px-5 py-4">
          <div>
            <h2 id="allocation-title" className="text-[0.9375rem] font-semibold text-[var(--rn-text)]">
              Allocation plan
            </h2>
            <p className="mt-0.5 text-xs text-[var(--rn-text-3)]">
              {request.zone} · {formatNumber(request.quantity_requested)} × {request.resource}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[var(--rn-text-3)] hover:text-[var(--rn-text)]"
            aria-label="Close dialog"
          >
            <Icon name="close" className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <ErrorState error={error} title="Could not build a plan" />
        ) : loading ? (
          <SkeletonTable rows={3} columns={3} />
        ) : (
          <>
            <div className="border-b border-[var(--rn-border)] px-5 py-4">
              <p className="ai-reasoning-box text-[0.8125rem] leading-relaxed">{plan.message}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone={plan.fully_satisfiable ? 'emerald' : 'amber'}>
                  {plan.coverage_pct}% coverage
                </Badge>
                {plan.confidence_score != null ? (
                  <Badge tone="indigo">{plan.confidence_score}% confidence</Badge>
                ) : null}
                {plan.shortage > 0 ? (
                  <Badge tone="red">Short {formatNumber(plan.shortage)}</Badge>
                ) : null}
              </div>
            </div>

            {plan.providers?.length ? (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th scope="col">Centre</th>
                      <th scope="col">Allocate</th>
                      <th scope="col">Stock after</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.providers.map((leg) => (
                      <tr key={leg.provider_id}>
                        <td>
                          <p className="font-medium text-[var(--rn-text)]">{leg.provider_name}</p>
                          <p className="mt-0.5 text-[0.6875rem] text-[var(--rn-text-3)]">
                            {leg.reasoning}
                          </p>
                        </td>
                        <td className="tabular-nums font-semibold text-[var(--rn-text)]">
                          {formatNumber(leg.allocate_qty)}
                        </td>
                        <td className="tabular-nums text-[var(--rn-text-3)]">
                          {formatNumber(leg.remaining_after)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            ) : (
              <EmptyState
                icon="box"
                title="No stock available"
                description={plan.message}
              />
            )}

            <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--rn-border)] px-5 py-4">
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button
                variant="primary"
                icon="truck"
                onClick={commit}
                loading={allocate.pending}
                disabled={!plan.providers?.length}
              >
                Dispatch {formatNumber(plan.providers?.reduce((sum, leg) => sum + leg.allocate_qty, 0) ?? 0)} units
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
    </Portal>
  );
}
