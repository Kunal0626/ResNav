/**
 * Typed-ish wrapper around the ResNav JSON API.
 *
 * In development `VITE_API_BASE_URL` is empty and Vite proxies `/api` to the
 * Flask server, so there is one origin and no CORS. In production it points at
 * the deployed backend.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

/** Requests that take longer than this are almost certainly a dead backend. */
const TIMEOUT_MS = 20000;

export class ApiError extends Error {
  constructor(message, { status, code, details } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True when retrying the same request could plausibly succeed. */
  get isRetryable() {
    return this.status === undefined || this.status >= 500;
  }
}

async function request(path, { method = 'GET', body, signal, timeout = TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  // Honour a caller-provided signal as well as our own timeout.
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort);

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        // Non-JSON body — surface the status rather than a parse error.
        throw new ApiError(`Unexpected response from the server (HTTP ${response.status}).`, {
          status: response.status,
        });
      }
    }

    if (!response.ok) {
      const error = payload?.error ?? {};
      throw new ApiError(error.message || `Request failed with status ${response.status}.`, {
        status: response.status,
        code: error.code,
        details: error.details,
      });
    }

    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error.name === 'AbortError') {
      // A caller-initiated abort is not a failure worth reporting.
      if (signal?.aborted) throw error;
      throw new ApiError('The server took too long to respond. Check that the backend is running.');
    }
    throw new ApiError('Could not reach the server. Check your connection and the API URL.');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}

const get = (path, options) => request(path, { ...options, method: 'GET' });
const post = (path, body, options) => request(path, { ...options, method: 'POST', body });

export const api = {
  health: (o) => get('/api/health', o),
  ready: (o) => get('/api/ready', o),

  overview: (o) => get('/api/overview', o),
  reference: (o) => get('/api/reference', o),

  search: (payload, o) => post('/api/search', payload, o),
  navigationEvent: (payload, o) => post('/api/navigation-events', payload, o),

  dashboard: (o) => get('/api/dashboard', o),
  forecast: (o) => get('/api/forecast', o),
  forecastSeries: (o) => get('/api/forecast/series', o),
  explorer: (o) => get('/api/explorer', o),

  stock: ({ lowOnly } = {}, o) => get(`/api/stock${lowOnly ? '?low=1' : ''}`, o),
  requests: ({ status } = {}, o) => get(`/api/requests${status ? `?status=${status}` : ''}`, o),
  createRequest: (payload, o) => post('/api/requests', payload, o),
  recommendation: (id, o) => get(`/api/requests/${id}/recommendation`, o),
  allocate: (id, payload, o) => post(`/api/requests/${id}/allocate`, payload ?? {}, o),
  updateRequestStatus: (id, status, o) => post(`/api/requests/${id}/status`, { status }, o),
  allocations: (o) => get('/api/allocations', o),
  logs: (o) => get('/api/logs', o),

  ai: {
    understand: (text, o) => post('/api/ai/nlp-understand', { text }, o),
    recommendProvider: (payload, o) => post('/api/ai/recommend-provider', payload, o),
    forecast: (o) => get('/api/ai/forecast', o),
    riskPredict: (o) => get('/api/ai/risk-predict', o),
    anomalyDetect: (o) => get('/api/ai/anomaly-detect', o),
    query: (query, o) => post('/api/ai/query', { query }, o),
    simulate: (payload, o) => post('/api/ai/simulate', payload, o),
    insights: (o) => get('/api/ai/insights', o),
  },
};
