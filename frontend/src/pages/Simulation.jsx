import { useCallback, useMemo, useState } from 'react';
import { Chart, PALETTE } from '../components/charts/Chart';
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
  Table,
  TableWrap,
} from '../components/ui';
import { useAction } from '../hooks/useApi';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { api } from '../lib/api';
import { SCENARIOS } from '../lib/constants';
import { formatNumber, formatPercent, titleCase } from '../lib/format';

const POPULATION_PRESETS = [10000, 50000, 100000, 500000, 1000000];
const MAX_POPULATION = 250000000;

/** Turns the engine's snake_case categories into readable labels. */
const label = (key) => titleCase(String(key).replace(/_/g, ' '));

export function Simulation() {
  useDocumentTitle('Simulation Lab');
  const [scenario, setScenario] = useState('flood');
  const [population, setPopulation] = useState(100000);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const simulate = useAction(useCallback((payload) => api.ai.simulate(payload), []));

  const onSubmit = async (event) => {
    event.preventDefault();
    const value = Number(population);
    if (!Number.isFinite(value) || value < 1 || value > MAX_POPULATION) {
      setError(`Enter a population between 1 and ${formatNumber(MAX_POPULATION)}.`);
      return;
    }
    setError(null);
    try {
      setResult(await simulate.execute({ scenario, population: value }));
    } catch {
      setResult(null);
    }
  };

  // Memoised so the array identity is stable for the dependent useMemo hooks.
  const shortages = useMemo(() => result?.shortages ?? [], [result]);
  const stats = result?.simulation_stats ?? {};

  // Demand vs. stock, driven by the P90 figure the engine plans against.
  const chartData = useMemo(() => {
    if (!shortages.length) return null;
    return {
      labels: shortages.map((row) => label(row.resource)),
      datasets: [
        {
          label: 'P90 demand',
          data: shortages.map((row) => Number(row.projected_demand_p90 ?? 0)),
          backgroundColor: PALETTE[0],
          borderRadius: 5,
        },
        {
          label: 'Stock on hand',
          data: shortages.map((row) => Number(row.current_stock ?? 0)),
          backgroundColor: PALETTE[3],
          borderRadius: 5,
        },
      ],
    };
  }, [shortages]);

  // Share of P90 demand the network can currently meet, across all resources.
  const coverage = useMemo(() => {
    if (!shortages.length) return null;
    const demand = shortages.reduce((sum, row) => sum + Number(row.projected_demand_p90 ?? 0), 0);
    const stock = shortages.reduce(
      (sum, row) => sum + Math.min(Number(row.current_stock ?? 0), Number(row.projected_demand_p90 ?? 0)),
      0,
    );
    return demand > 0 ? (stock / demand) * 100 : 100;
  }, [shortages]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="AI Intelligence"
        title="Simulation Lab"
        description="Monte Carlo modelling of resource demand for a disaster scenario, compared against current inventory."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="overflow-hidden lg:sticky lg:top-20 lg:self-start">
          <CardHeader title="Scenario" icon="beaker" />
          <CardBody>
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <Field label="Disaster type" htmlFor="scenario">
                <Select
                  id="scenario"
                  value={scenario}
                  onChange={(event) => setScenario(event.target.value)}
                >
                  {SCENARIOS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field
                label="Affected population"
                htmlFor="population"
                error={error}
                hint="The model samples 5–25% of this as directly affected."
              >
                <Input
                  id="population"
                  type="number"
                  min="1"
                  max={MAX_POPULATION}
                  step="1000"
                  value={population}
                  invalid={Boolean(error)}
                  onChange={(event) => setPopulation(event.target.value)}
                />
              </Field>

              <div className="flex flex-wrap gap-1.5">
                {POPULATION_PRESETS.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setPopulation(preset)}
                    aria-pressed={Number(population) === preset}
                    className={`rounded-full px-2.5 py-1 text-[0.6875rem] font-medium transition-colors ${
                      Number(population) === preset
                        ? 'bg-indigo-500 text-white'
                        : 'bg-[var(--rn-border)]/60 text-[var(--rn-text-2)] hover:bg-[var(--rn-border)]'
                    }`}
                  >
                    {formatNumber(preset, { compact: true })}
                  </button>
                ))}
              </div>

              <Button
                type="submit"
                variant="ai"
                icon="beaker"
                className="w-full"
                loading={simulate.pending}
              >
                Run simulation
              </Button>
            </form>
          </CardBody>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          {simulate.error ? (
            <Card>
              <ErrorState error={simulate.error} title="Simulation failed" />
            </Card>
          ) : simulate.pending ? (
            <SkeletonCard rows={6} />
          ) : !result ? (
            <Card>
              <EmptyState
                icon="beaker"
                title="No simulation run yet"
                description="Pick a scenario and an affected population, then run the model to see projected demand against current stock."
              />
            </Card>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <StatTile label="Scenario" value={result.scenario} />
                <StatTile
                  label="Iterations"
                  value={formatNumber(stats.iterations, { compact: true })}
                />
                <StatTile
                  label="P90 coverage"
                  value={coverage == null ? '—' : formatPercent(coverage)}
                  tone={coverage > 70 ? 'emerald' : coverage > 40 ? 'amber' : 'red'}
                />
              </div>

              <Card>
                <CardBody className="space-y-3">
                  <p className="text-[0.9375rem] font-semibold text-[var(--rn-text)]">
                    {result.scenario_description}
                  </p>
                  <p className="ai-reasoning-box text-xs leading-relaxed">{result.explanation}</p>
                  <dl className="grid grid-cols-2 gap-3 pt-1 sm:grid-cols-4">
                    <Meta label="Population" value={formatNumber(stats.population, { compact: true })} />
                    <Meta label="Duration" value={stats.duration_range} />
                    <Meta label="Supply disruption" value={stats.supply_chain_disruption} />
                    <Meta label="Resources modelled" value={shortages.length} />
                  </dl>
                </CardBody>
              </Card>

              {chartData ? (
                <Card className="overflow-hidden">
                  <CardHeader
                    title="P90 Demand vs. Stock on Hand"
                    subtitle="P90 is the level that covers 90% of simulated outcomes"
                    icon="chart"
                  />
                  <div className="p-5">
                    <Chart
                      type="bar"
                      data={chartData}
                      height={300}
                      ariaLabel="Grouped bar chart comparing P90 projected demand against current stock per resource"
                      options={{ plugins: { legend: { display: true, position: 'bottom' } } }}
                    />
                  </div>
                </Card>
              ) : null}

              {shortages.length ? (
                <Card className="overflow-hidden">
                  <CardHeader
                    title="Projected Shortages"
                    subtitle="Probability that demand exceeds available stock"
                    icon="alert"
                  />
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <th scope="col">Resource</th>
                          <th scope="col">Stock</th>
                          <th scope="col">P90 demand</th>
                          <th scope="col">Shortfall</th>
                          <th scope="col">Probability</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shortages.map((row) => (
                          <tr key={row.resource}>
                            <td className="font-medium text-[var(--rn-text)]">
                              {label(row.resource)}
                            </td>
                            <td className="tabular-nums">{formatNumber(row.current_stock)}</td>
                            <td className="tabular-nums">
                              {formatNumber(row.projected_demand_p90)}
                            </td>
                            <td className="tabular-nums">{formatNumber(row.shortage_amount)}</td>
                            <td className="w-32">
                              <div className="flex items-center gap-2">
                                <Progress
                                  value={row.shortage_probability}
                                  tone={
                                    row.shortage_probability > 66
                                      ? 'red'
                                      : row.shortage_probability > 33
                                        ? 'amber'
                                        : 'emerald'
                                  }
                                  label={`Shortage probability for ${label(row.resource)}`}
                                  className="flex-1"
                                />
                                <span className="mono w-9 shrink-0 text-right text-[0.6875rem] tabular-nums">
                                  {Math.round(row.shortage_probability)}%
                                </span>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                </Card>
              ) : null}

              {result.recommended_allocations?.length ? (
                <Card className="overflow-hidden">
                  <CardHeader
                    title="Recommended Pre-positioning"
                    subtitle="Quantities that would reach P90 coverage"
                    icon="truck"
                  />
                  <ul className="divide-y divide-[var(--rn-border)]">
                    {result.recommended_allocations.map((row) => (
                      <li key={row.resource} className="flex items-start gap-3 px-5 py-4">
                        <Badge
                          tone={row.priority === 'critical' ? 'red' : 'amber'}
                          className="mt-0.5 shrink-0"
                        >
                          {row.priority}
                        </Badge>
                        <div className="min-w-0 flex-1">
                          <p className="text-[0.8125rem] font-medium text-[var(--rn-text)]">
                            {label(row.resource)} — {formatNumber(row.recommended_qty)} units
                          </p>
                          <p className="mt-0.5 text-xs leading-relaxed text-[var(--rn-text-3)]">
                            {row.explanation}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>
              ) : null}

              {result.insights?.length ? (
                <Card className="overflow-hidden">
                  <CardHeader title="Simulation Insights" icon="bulb" />
                  <ul className="divide-y divide-[var(--rn-border)]">
                    {result.insights.map((insight, index) => (
                      <li
                        key={index}
                        className="px-5 py-3 text-[0.8125rem] leading-relaxed text-[var(--rn-text-2)]"
                      >
                        {insight}
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

function StatTile({ label: text, value, tone = 'indigo' }) {
  const tones = {
    indigo: 'text-indigo-500',
    emerald: 'text-emerald-500',
    amber: 'text-amber-500',
    red: 'text-red-500',
  };
  return (
    <div className="dash-card p-5">
      <p className="kpi-label">{text}</p>
      <p className={`mt-1.5 text-xl font-bold tabular-nums ${tones[tone]}`}>{value ?? '—'}</p>
    </div>
  );
}

function Meta({ label: text, value }) {
  return (
    <div>
      <dt className="text-[0.6875rem] uppercase tracking-wide text-[var(--rn-text-3)]">{text}</dt>
      <dd className="mt-0.5 text-xs font-semibold text-[var(--rn-text)]">{value ?? '—'}</dd>
    </div>
  );
}
