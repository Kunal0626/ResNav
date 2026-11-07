import { useCallback, useState } from 'react';
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
  Progress,
  Select,
  SkeletonCard,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useAction, useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useGeolocation } from '../hooks/useGeolocation';
import { api } from '../lib/api';
import { formatDistance, formatNumber, formatPercent } from '../lib/format';

const URGENCY_OPTIONS = [
  { value: 1, label: 'Routine (1.0×)' },
  { value: 1.5, label: 'Elevated (1.5×)' },
  { value: 2, label: 'Urgent (2.0×)' },
  { value: 3, label: 'Critical (3.0×)' },
];

export function Recommend() {
  useDocumentTitle('Recommendation Engine');
  const { coords, fallback } = useGeolocation();

  const referenceFetcher = useCallback(({ signal }) => api.reference({ signal }), []);
  const { data: reference, loading: referenceLoading } = useApi(referenceFetcher);

  const [form, setForm] = useState({ resource_id: '', quantity_requested: 100, urgency: 1.5 });
  const [result, setResult] = useState(null);
  const [validation, setValidation] = useState({});

  const recommend = useAction(
    useCallback(
      (payload) =>
        api.ai.recommendProvider({
          ...payload,
          latitude: coords.latitude,
          longitude: coords.longitude,
        }),
      [coords.latitude, coords.longitude],
    ),
  );

  const onSubmit = async (event) => {
    event.preventDefault();

    const errors = {};
    if (!form.resource_id) errors.resource_id = 'Select a resource.';
    const quantity = Number(form.quantity_requested);
    if (!Number.isFinite(quantity) || quantity <= 0) {
      errors.quantity_requested = 'Enter a quantity greater than zero.';
    }
    setValidation(errors);
    if (Object.keys(errors).length) return;

    try {
      setResult(
        await recommend.execute({
          resource_id: Number(form.resource_id),
          quantity_requested: quantity,
          urgency: Number(form.urgency),
        }),
      );
    } catch {
      setResult(null);
    }
  };

  const best = result?.recommended_provider ?? null;
  const scored = result?.all_scored ?? [];
  // The top entry is rendered separately as the headline recommendation.
  const runnersUp = scored.slice(1);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Provider Recommendation"
        description="Scores every centre holding the requested resource on stock coverage, reliability, proximity and urgency, then explains the ranking."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="overflow-hidden lg:sticky lg:top-20 lg:self-start">
          <CardHeader title="Parameters" icon="filter" />
          <CardBody>
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <Field
                label="Resource"
                htmlFor="resource"
                required
                error={validation.resource_id}
                hint="Only centres holding this resource are considered."
              >
                <Select
                  id="resource"
                  value={form.resource_id}
                  onChange={(event) => setForm({ ...form, resource_id: event.target.value })}
                  disabled={referenceLoading}
                >
                  <option value="">
                    {referenceLoading ? 'Loading resources…' : 'Select a resource'}
                  </option>
                  {(reference?.resources ?? []).map((resource) => (
                    <option key={resource.id} value={resource.id}>
                      {resource.name}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field
                label="Quantity needed"
                htmlFor="quantity"
                required
                error={validation.quantity_requested}
              >
                <Input
                  id="quantity"
                  type="number"
                  min="1"
                  step="1"
                  value={form.quantity_requested}
                  invalid={Boolean(validation.quantity_requested)}
                  onChange={(event) =>
                    setForm({ ...form, quantity_requested: event.target.value })
                  }
                />
              </Field>

              <Field label="Urgency" htmlFor="urgency" hint="Weights the final score.">
                <Select
                  id="urgency"
                  value={form.urgency}
                  onChange={(event) => setForm({ ...form, urgency: event.target.value })}
                >
                  {URGENCY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>

              <p className="text-[0.6875rem] leading-relaxed text-[var(--rn-text-3)]">
                <Icon name="location" className="mr-1 inline h-3 w-3" />
                Distances measured from{' '}
                {fallback ? 'Delhi (default origin)' : 'your current location'}.
              </p>

              <Button
                type="submit"
                variant="ai"
                icon="bulb"
                className="w-full"
                loading={recommend.pending}
              >
                Recommend providers
              </Button>
            </form>
          </CardBody>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          {recommend.error ? (
            <Card>
              <ErrorState error={recommend.error} title="Recommendation failed" />
            </Card>
          ) : recommend.pending ? (
            <SkeletonCard rows={5} />
          ) : !result ? (
            <Card>
              <EmptyState
                icon="users"
                title="No recommendation yet"
                description="Choose a resource and quantity, then run the engine to see a ranked list of centres with the reasoning behind each score."
              />
            </Card>
          ) : !best ? (
            <Card>
              <EmptyState
                icon="box"
                title="No centre holds this resource"
                description={
                  result.explanation ??
                  'Nothing in the network currently has stock of the selected resource.'
                }
              />
            </Card>
          ) : (
            <>
              <Card className="overflow-hidden border-indigo-500/30">
                <CardHeader
                  title="Recommended"
                  subtitle="Highest-scoring centre for these parameters"
                  icon="check"
                  action={
                    <Badge tone="indigo">{result.confidence_score}% confidence</Badge>
                  }
                />
                <CardBody>
                  <ProviderDetail provider={best} highlight />
                </CardBody>
              </Card>

              {result.explanation ? (
                <Card>
                  <CardBody>
                    <p className="ai-reasoning-box text-xs leading-relaxed">{result.explanation}</p>
                  </CardBody>
                </Card>
              ) : null}

              {runnersUp.length ? (
                <Card className="overflow-hidden">
                  <CardHeader
                    title="Other Candidates"
                    subtitle={`${runnersUp.length} further centres, ranked`}
                    icon="users"
                  />
                  <ul className="divide-y divide-[var(--rn-border)]">
                    {runnersUp.map((provider, index) => (
                      <li key={provider.provider_id} className="px-5 py-4">
                        <ProviderDetail provider={provider} rank={index + 2} />
                      </li>
                    ))}
                  </ul>
                </Card>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ProviderDetail({ provider, rank, highlight = false }) {
  // `ai_score` is 0–1; the UI shows it as a percentage.
  const score = Number(provider.ai_score ?? 0) * 100;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          {rank ? (
            <span
              className="mono flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--rn-border)]/70 text-xs font-bold text-[var(--rn-text-2)]"
              aria-label={`Rank ${rank}`}
            >
              {rank}
            </span>
          ) : null}
          <div className="min-w-0">
            <h3
              className={`truncate font-semibold text-[var(--rn-text)] ${
                highlight ? 'text-base' : 'text-[0.875rem]'
              }`}
            >
              {provider.provider_name}
            </h3>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-[var(--rn-text-3)]">
              <span className="inline-flex items-center gap-1">
                <Icon name="location" className="h-3 w-3" />
                {provider.provider_city}
              </span>
              <span>{formatDistance(provider.distance_km)}</span>
            </p>
          </div>
        </div>
        <Badge tone={score > 66 ? 'emerald' : score > 40 ? 'indigo' : 'amber'}>
          Score {score.toFixed(0)}
        </Badge>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Metric label="Stock" value={formatNumber(provider.stock_level)} />
        <Metric label="Reliability" value={formatPercent(provider.reliability_score * 100)} />
        <Metric label="Success rate" value={formatPercent(provider.success_rate * 100)} />
      </dl>

      <div className="mt-4">
        <Progress
          value={score}
          tone={score > 66 ? 'emerald' : score > 40 ? 'accent' : 'amber'}
          label={`Recommendation score for ${provider.provider_name}`}
        />
      </div>

      {provider.reasoning ? (
        <p className="ai-reasoning-box mt-3 text-[0.6875rem] leading-relaxed">
          {provider.reasoning}
        </p>
      ) : null}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <dt className="text-[0.6875rem] uppercase tracking-wide text-[var(--rn-text-3)]">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold tabular-nums text-[var(--rn-text)]">{value}</dd>
    </div>
  );
}
