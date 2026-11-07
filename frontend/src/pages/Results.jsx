import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Input,
  Progress,
  SkeletonCard,
} from '../components/ui';
import { Icon } from '../components/ui/Icon';
import { useApi } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { useToast } from '../contexts/ToastContext';
import { api } from '../lib/api';
import { DEFAULT_COORDS } from '../lib/constants';
import { formatDistance, formatNumber } from '../lib/format';

export function Results() {
  useDocumentTitle('Search Results');
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  const initial = location.state ?? {};
  const [query, setQuery] = useState(initial.query ?? '');
  const [submitted, setSubmitted] = useState(initial.query ?? '');
  const coords = initial.coords ?? DEFAULT_COORDS;

  // Landing here directly (refresh, shared link) has no query to run.
  useEffect(() => {
    if (!initial.query) navigate('/', { replace: true });
  }, [initial.query, navigate]);

  const fetchResults = useCallback(
    ({ signal }) =>
      api.search(
        { query: submitted, latitude: coords.latitude, longitude: coords.longitude },
        { signal },
      ),
    [submitted, coords.latitude, coords.longitude],
  );

  const { data, error, loading, refresh } = useApi(fetchResults, {
    enabled: Boolean(submitted),
    deps: [submitted],
  });

  const onSubmit = (event) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (trimmed) setSubmitted(trimmed);
  };

  const openDirections = async (result) => {
    try {
      const { url } = await api.navigationEvent({
        latitude: result.latitude,
        longitude: result.longitude,
        provider_id: result.id,
      });
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      // Logging the click is incidental; never block navigation on it.
      window.open(result.nav_url, '_blank', 'noopener,noreferrer');
    }
  };

  const results = data?.results ?? [];

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden">
        <div className="p-5 sm:p-6">
          <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <span
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--rn-text-3)]"
                aria-hidden="true"
              >
                <Icon name="search" className="h-4 w-4" />
              </span>
              <label className="sr-only" htmlFor="results-search">
                Refine your search
              </label>
              <Input
                id="results-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="pl-10"
                maxLength={500}
              />
            </div>
            <Button type="submit" variant="ai" icon="search" loading={loading}>
              Search
            </Button>
          </form>

          {data ? (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Badge tone="indigo" dot>
                {data.detected_intent}
              </Badge>
              <Badge tone={confidenceTone(data.confidence)}>
                {formatNumber(data.confidence)}% confidence
              </Badge>
              {data.nlp?.extracted_quantity ? (
                <Badge tone="cyan">Quantity: {formatNumber(data.nlp.extracted_quantity)}</Badge>
              ) : null}
              {data.nlp?.urgency_score > 1.2 ? (
                <Badge tone="red">Urgent ({data.nlp.urgency_score.toFixed(2)}×)</Badge>
              ) : null}
              {data.origin?.fallback ? (
                <Badge tone="slate">Default origin (Delhi)</Badge>
              ) : null}
            </div>
          ) : null}

          {data?.nlp?.explanation ? (
            <p className="ai-reasoning-box mt-4 text-xs leading-relaxed">
              {data.nlp.explanation}
            </p>
          ) : null}
        </div>
      </Card>

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={refresh} title="Search failed" />
        </Card>
      ) : loading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((index) => (
            <SkeletonCard key={index} rows={2} />
          ))}
        </div>
      ) : results.length === 0 ? (
        <Card>
          <EmptyState
            icon="search"
            title="No matching centres"
            description="Try describing the need differently — for example 'medical supplies' instead of a brand name — or widen the resource type."
            action={
              <Button variant="ghost" size="sm" to="/" icon="home">
                Back to overview
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-3">
          <div className="space-y-4 xl:col-span-2">
            <p className="text-xs text-[var(--rn-text-3)]">
              Showing {results.length} of {formatNumber(data.total)} ranked centres
            </p>
            {results.map((result, index) => (
              <ResultCard
                key={result.id}
                result={result}
                rank={index + 1}
                onDirections={() => openDirections(result)}
                onCopy={() => {
                  navigator.clipboard
                    ?.writeText(`${result.name}, ${result.address ?? result.city}`)
                    .then(() => toast.success('Address copied to clipboard.'))
                    .catch(() => toast.error('Could not copy the address.'));
                }}
              />
            ))}
          </div>

          <div className="space-y-4">
            {data.map_embed_url ? (
              <Card className="overflow-hidden">
                <CardHeader title="Route to top match" icon="location" />
                <iframe
                  title="Directions to the highest-ranked relief centre"
                  src={data.map_embed_url}
                  className="h-72 w-full border-0"
                  loading="lazy"
                  referrerPolicy="no-referrer-when-downgrade"
                />
              </Card>
            ) : null}

            {data.emergency_contacts?.length ? (
              <Card className="overflow-hidden">
                <CardHeader title="Emergency Helplines" icon="phone" />
                <ul className="divide-y divide-[var(--rn-border)]">
                  {data.emergency_contacts.map((contact) => (
                    <li
                      key={`${contact.name}-${contact.number}`}
                      className="flex items-center justify-between gap-3 px-5 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-[var(--rn-text)]">
                          {contact.name}
                        </p>
                        <p className="text-[0.6875rem] text-[var(--rn-text-3)]">{contact.scope}</p>
                      </div>
                      <a
                        href={`tel:${contact.number}`}
                        className="mono shrink-0 text-xs font-semibold text-indigo-500 hover:underline"
                      >
                        {contact.number}
                      </a>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function ResultCard({ result, rank, onDirections, onCopy }) {
  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-[var(--shadow-card-hover)]">
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 gap-3">
            <span
              className="mono flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-xs font-bold text-indigo-500"
              aria-label={`Rank ${rank}`}
            >
              {rank}
            </span>
            <div className="min-w-0">
              <h2 className="truncate text-[0.9375rem] font-semibold text-[var(--rn-text)]">
                {result.name}
              </h2>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--rn-text-3)]">
                <span className="inline-flex items-center gap-1">
                  <Icon name="location" className="h-3 w-3" />
                  {[result.city, result.state].filter(Boolean).join(', ')}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Icon name="clock" className="h-3 w-3" />
                  {result.is_24_7 ? 'Open 24/7' : (result.operating_hours ?? 'Hours not listed')}
                </span>
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Badge tone="indigo">{formatDistance(result.distance_km)}</Badge>
            <Badge tone={result.stock_availability > 0 ? 'emerald' : 'slate'}>
              {formatNumber(result.stock_availability)} units
            </Badge>
          </div>
        </div>

        {result.description ? (
          <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-[var(--rn-text-2)]">
            {result.description}
          </p>
        ) : null}

        <div className="mt-4">
          <div className="mb-1.5 flex items-center justify-between text-[0.6875rem]">
            <span className="text-[var(--rn-text-3)]">AI match score</span>
            <span className="mono font-semibold text-[var(--rn-text)]">
              {result.combined_score.toFixed(1)}
            </span>
          </div>
          <Progress
            value={result.combined_score}
            tone={result.combined_score > 60 ? 'emerald' : result.combined_score > 35 ? 'accent' : 'amber'}
            label={`Match score for ${result.name}`}
          />
        </div>

        <details className="mt-3 group">
          <summary className="cursor-pointer list-none text-[0.6875rem] font-medium text-indigo-500 hover:underline">
            Why this centre?
          </summary>
          <p className="ai-reasoning-box mt-2 text-[0.6875rem] leading-relaxed">{result.why}</p>
        </details>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" icon="location" onClick={onDirections}>
            Directions
          </Button>
          {result.phone ? (
            <Button variant="ghost" size="sm" icon="phone" href={`tel:${result.phone}`}>
              {result.phone}
            </Button>
          ) : null}
          <Button variant="ghost" size="sm" icon="clipboard" onClick={onCopy}>
            Copy address
          </Button>
        </div>
      </div>
    </Card>
  );
}

function confidenceTone(confidence) {
  if (confidence >= 70) return 'emerald';
  if (confidence >= 45) return 'amber';
  return 'red';
}
