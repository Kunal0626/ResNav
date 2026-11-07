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
  PageHeader,
  Progress,
  SkeletonCard,
  Textarea,
} from '../components/ui';
import { useAction } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { formatNumber, titleCase } from '../lib/format';

const EXAMPLES = [
  'We urgently need 500 water packets for a flooded village',
  '200 families require shelter and blankets tonight',
  'Medical supplies and first aid running low at the camp',
  'Need food rations for 1500 people, situation is critical',
];

const MAX_LENGTH = 2000;

export function NlpConsole() {
  useDocumentTitle('NLP Console');
  const [text, setText] = useState('');
  const [understanding, setUnderstanding] = useState(null);
  const [answer, setAnswer] = useState(null);

  const understand = useAction(useCallback((value) => api.ai.understand(value), []));
  const askQuestion = useAction(useCallback((value) => api.ai.query(value), []));

  const analyse = async (event) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    setAnswer(null);
    try {
      setUnderstanding(await understand.execute(trimmed));
    } catch {
      setUnderstanding(null);
    }
  };

  const ask = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setUnderstanding(null);
    try {
      setAnswer(await askQuestion.execute(trimmed));
    } catch {
      setAnswer(null);
    }
  };

  const pending = understand.pending || askQuestion.pending;
  const error = understand.error || askQuestion.error;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Tools"
        title="NLP Console"
        description="Parse a relief request into structured intent, quantity and urgency — or ask a question about the current operational data."
      />

      <Card className="overflow-hidden">
        <CardHeader title="Input" icon="chat" />
        <CardBody>
          <form onSubmit={analyse} className="space-y-4">
            <Field
              label="Request or question"
              htmlFor="nlp-input"
              hint={`${text.length} / ${MAX_LENGTH} characters`}
            >
              <Textarea
                id="nlp-input"
                rows={4}
                maxLength={MAX_LENGTH}
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Describe a need, or ask something like 'which zone has the highest risk?'"
              />
            </Field>

            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="ai" icon="chat" loading={understand.pending} disabled={!text.trim()}>
                Analyse request
              </Button>
              <Button
                type="button"
                variant="ghost"
                icon="search"
                onClick={ask}
                loading={askQuestion.pending}
                disabled={!text.trim()}
              >
                Ask the data
              </Button>
            </div>
          </form>

          <div className="mt-5 border-t border-[var(--rn-border)] pt-4">
            <p className="mb-2 text-[0.6875rem] font-semibold uppercase tracking-wide text-[var(--rn-text-3)]">
              Try an example
            </p>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setText(example)}
                  className="search-suggestion-item rounded-full px-3 py-1.5 text-left text-[0.6875rem] text-[var(--rn-text-2)]"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        </CardBody>
      </Card>

      {error ? (
        <Card>
          <ErrorState error={error} title="Analysis failed" />
        </Card>
      ) : pending ? (
        <SkeletonCard rows={5} />
      ) : understanding ? (
        <UnderstandingResult result={understanding} />
      ) : answer ? (
        <AnswerResult result={answer} />
      ) : (
        <Card>
          <EmptyState
            icon="chat"
            title="Nothing analysed yet"
            description="Enter a request above to see how the classifier interprets it, or ask a question to query the live data."
          />
        </Card>
      )}
    </div>
  );
}

function UnderstandingResult({ result }) {
  const confidence = Number(result.confidence ?? 0);
  const pct = confidence <= 1 ? confidence * 100 : confidence;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="overflow-hidden">
        <CardHeader title="Detected Intent" icon="bulb" />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="indigo" dot>
              {result.detected_intent ?? result.intent ?? 'unknown'}
            </Badge>
            <Badge tone={pct > 70 ? 'emerald' : pct > 45 ? 'amber' : 'red'}>
              {pct.toFixed(0)}% confidence
            </Badge>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between text-[0.6875rem] text-[var(--rn-text-3)]">
              <span>Classification confidence</span>
              <span className="mono">{pct.toFixed(1)}%</span>
            </div>
            <Progress
              value={pct}
              tone={pct > 70 ? 'emerald' : pct > 45 ? 'amber' : 'red'}
              label="Classification confidence"
            />
          </div>

          {result.explanation ? (
            <p className="ai-reasoning-box text-xs leading-relaxed">{result.explanation}</p>
          ) : null}
        </CardBody>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Extracted Entities" icon="filter" />
        <CardBody>
          <dl className="grid grid-cols-2 gap-4">
            <Entity
              label="Quantity"
              value={
                result.extracted_quantity != null || result.quantity != null
                  ? formatNumber(result.extracted_quantity ?? result.quantity)
                  : 'Not stated'
              }
            />
            <Entity
              label="Urgency"
              value={
                result.urgency_score != null
                  ? `${Number(result.urgency_score).toFixed(2)}×`
                  : (result.urgency ?? '—')
              }
            />
            <Entity
              label="Resource"
              value={
                result.resources?.length
                  ? result.resources.map((r) => titleCase(r.category)).join(', ')
                  : (result.resource ?? '—')
              }
            />
            <Entity
              label="Multi-resource"
              value={result.is_multi_resource || result.resources?.length > 1 ? 'Yes' : 'No'}
            />
          </dl>

          {result.resources?.length ? (
            <div className="mt-5 border-t border-[var(--rn-border)] pt-4">
              <p className="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-[var(--rn-text-3)]">
                Matched resource categories
              </p>
              <ul className="space-y-2.5">
                {result.resources.map((resource) => (
                  <li key={resource.category}>
                    <div className="flex items-center gap-3">
                      <span className="w-24 shrink-0 truncate text-xs font-medium text-[var(--rn-text)]">
                        {titleCase(resource.category)}
                      </span>
                      <Progress
                        value={resource.confidence * 100}
                        className="flex-1"
                        label={`${resource.category} confidence`}
                      />
                      <span className="mono w-10 shrink-0 text-right text-[0.6875rem] tabular-nums text-[var(--rn-text-3)]">
                        {(resource.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    {resource.description ? (
                      <p className="ml-27 mt-1 text-[0.6875rem] text-[var(--rn-text-3)]">
                        {resource.description}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {Array.isArray(result.top_3) && result.top_3.length ? (
            <div className="mt-5 border-t border-[var(--rn-border)] pt-4">
              <p className="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-[var(--rn-text-3)]">
                Closest categories
              </p>
              <ul className="space-y-2">
                {result.top_3.map((entry) => {
                  const [name, score] = Array.isArray(entry) ? entry : [entry.name, entry.score];
                  const value = Number(score) * 100;
                  return (
                    <li key={name} className="flex items-center gap-3">
                      <span className="w-24 shrink-0 truncate text-xs text-[var(--rn-text-2)]">
                        {name}
                      </span>
                      <Progress value={value} className="flex-1" label={`${name} similarity`} />
                      <span className="mono w-10 shrink-0 text-right text-[0.6875rem] tabular-nums text-[var(--rn-text-3)]">
                        {value.toFixed(0)}%
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}

function AnswerResult({ result }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Answer"
        subtitle={result.matched_template?.replace(/_/g, ' ')}
        icon="search"
      />
      <CardBody className="space-y-4">
        <p className="text-[0.9375rem] leading-relaxed text-[var(--rn-text)]">
          {result.answer ?? result.message ?? 'No answer could be derived from the current data.'}
        </p>

        {result.match_confidence != null ? (
          <Badge tone="indigo">
            {(Number(result.match_confidence) * 100).toFixed(0)}% template match
          </Badge>
        ) : null}

        {Array.isArray(result.data) && result.data.length ? (
          <ul className="space-y-1.5 border-t border-[var(--rn-border)] pt-4">
            {result.data.slice(0, 10).map((row, index) => (
              <li key={index} className="mono text-xs text-[var(--rn-text-2)]">
                {typeof row === 'object' ? Object.values(row).join(' · ') : String(row)}
              </li>
            ))}
          </ul>
        ) : null}

        {result.explanation ? (
          <p className="ai-reasoning-box text-xs leading-relaxed">{result.explanation}</p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function Entity({ label, value }) {
  return (
    <div>
      <dt className="text-[0.6875rem] uppercase tracking-wide text-[var(--rn-text-3)]">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-[var(--rn-text)]">{value}</dd>
    </div>
  );
}
