/**
 * The read-only demo transport.
 *
 * The deployed demo has no backend: it is the real SPA served from a CDN with
 * every GET answered from JSON that `tools/snapshot_demo.py` captured from a
 * live API run. So the pages show real seeded data, not fixtures.
 *
 * What cannot be captured is a write. A static file answers GET and nothing
 * else, and there is no database behind the demo to change. Rather than fake
 * a success, those calls raise `DemoUnavailableError` and the UI says the
 * action needs the live backend. Search is the one exception worth making:
 * it is a POST, it is the landing page's whole purpose, and a fixed set of
 * example queries was recorded from the live ranker -- so those answers are
 * genuine, and anything else is refused rather than guessed at.
 */

import { ApiError } from './apiError.js';

export const isDemo = import.meta.env.VITE_DEMO_MODE === 'true';

/** Where the snapshots are served from, relative to the site root. */
const DEMO_ROOT = '/demo';

/**
 * An action that only exists against a real backend.
 *
 * Extends ApiError so every page's existing error branch renders it; the
 * `isDemoLimit` flag lets the UI style it as a limitation rather than a
 * fault, because nothing is actually broken.
 */
export class DemoUnavailableError extends ApiError {
  constructor(message, { examples } = {}) {
    super(message);
    this.name = 'DemoUnavailableError';
    this.isDemoLimit = true;
    this.examples = examples;
  }

  /** Retrying cannot help: there is no backend to reach. */
  get isRetryable() {
    return false;
  }
}

let manifestPromise = null;

/** The capture manifest, fetched once and shared. */
export function manifest() {
  manifestPromise ??= fetch(`${DEMO_ROOT}/manifest.json`)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
    .catch(() => ({ searches: {}, recommendations: [], statuses: [] }));
  return manifestPromise;
}

async function snapshot(name, { signal } = {}) {
  const response = await fetch(`${DEMO_ROOT}/${name}.json`, { signal });
  if (!response.ok) {
    throw new DemoUnavailableError(
      'This view was not captured in the demo snapshot.',
    );
  }
  return response.json();
}

/** Same slug rule as tools/snapshot_demo.py, so filenames line up. */
function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

/** The example queries the demo can answer, in the order they were recorded. */
export async function exampleQueries() {
  return Object.keys((await manifest()).searches ?? {});
}

/** Refused because it would change data, and there is no database here. */
const writeRefused = (what) =>
  Promise.reject(
    new DemoUnavailableError(
      `${what} would change data, and this demo is a folder of static files with ` +
        'no database behind it. Clone the repository and run it to use this.',
    ),
  );

/** Refused because the model runs on the server, and there is no server. */
const computeRefused = (what) =>
  Promise.reject(
    new DemoUnavailableError(
      `${what} runs on the server, and this demo is served as static files with ` +
        'nothing behind them. Clone the repository and run it to use this.',
    ),
  );

export const demoApi = {
  health: (o) => snapshot('health', o),
  ready: (o) => snapshot('ready', o),

  overview: (o) => snapshot('overview', o),
  reference: (o) => snapshot('reference', o),

  async search(payload, o) {
    const key = slug(payload?.query ?? '');
    const { searches = {} } = await manifest();
    const name = Object.values(searches).includes(key) ? key : null;
    if (!name) {
      throw new DemoUnavailableError(
        'The demo answers a fixed set of example searches, because the ranker ' +
          'runs on the server and this deployment has none. Pick one below, or ' +
          'run the project locally to search freely.',
        { examples: Object.keys(searches) },
      );
    }
    return snapshot(`search-${name}`, o);
  },

  // Telemetry. Nothing records it in the demo and nothing depends on the
  // result, so it succeeds quietly rather than erroring in the console.
  navigationEvent: () => Promise.resolve({ ok: true, recorded: false }),

  dashboard: (o) => snapshot('dashboard', o),
  forecast: (o) => snapshot('forecast', o),
  forecastSeries: (o) => snapshot('forecast-series', o),
  explorer: (o) => snapshot('explorer', o),

  stock: ({ lowOnly } = {}, o) => snapshot(lowOnly ? 'stock-low' : 'stock', o),
  requests: ({ status } = {}, o) => snapshot(status ? `requests-${slug(status)}` : 'requests', o),
  recommendation: (id, o) => snapshot(`recommendation-${id}`, o),
  allocations: (o) => snapshot('allocations', o),
  logs: (o) => snapshot('logs', o),

  createRequest: () => writeRefused('Creating a request'),
  allocate: () => writeRefused('Running an allocation'),
  updateRequestStatus: () => writeRefused('Changing a request’s status'),

  ai: {
    forecast: (o) => snapshot('ai-forecast', o),
    riskPredict: (o) => snapshot('ai-risk', o),
    anomalyDetect: (o) => snapshot('ai-anomaly', o),
    insights: (o) => snapshot('ai-insights', o),

    understand: () => computeRefused('Parsing free text'),
    recommendProvider: () => computeRefused('Scoring providers'),
    query: () => computeRefused('Answering a question'),
    simulate: () => computeRefused('The Monte Carlo simulation'),
  },
};
