/**
 * The error type every API call rejects with.
 *
 * It lives in its own module so that both the live client (`api.js`) and the
 * demo client (`demo.js`) can use it. Putting it in `api.js` created an
 * import cycle -- `api.js` chooses between the two clients, so it imports
 * `demo.js`, which needs this class before `api.js` has finished evaluating.
 */

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
