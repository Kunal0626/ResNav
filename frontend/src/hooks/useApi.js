import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Fetch on mount, with cancellation, retry and a stable `refresh`.
 *
 * `fetcher` receives `{ signal }` and must be referentially stable — wrap it in
 * `useCallback` at the call site, or pass a module-level function.
 */
export function useApi(fetcher, { enabled = true, deps = [] } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  const controllerRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const run = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setState((current) => ({ ...current, loading: true, error: null }));
    try {
      const data = await fetcher({ signal: controller.signal });
      if (mountedRef.current && !controller.signal.aborted) {
        setState({ data, error: null, loading: false });
      }
    } catch (error) {
      // An abort means a newer request superseded this one, or we unmounted.
      if (error.name === 'AbortError' || controller.signal.aborted) return;
      if (mountedRef.current) setState({ data: null, error, loading: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher]);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false });
      return undefined;
    }
    run();
    return () => controllerRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run, ...deps]);

  return { ...state, refresh: run };
}

/**
 * An action the user triggers (submit, allocate). Tracks its own pending and
 * error state so buttons can disable themselves and forms can show failures.
 */
export function useAction(action) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);

  const execute = useCallback(
    async (...args) => {
      setPending(true);
      setError(null);
      try {
        return await action(...args);
      } catch (caught) {
        setError(caught);
        throw caught;
      } finally {
        setPending(false);
      }
    },
    [action],
  );

  return { execute, pending, error, reset: () => setError(null) };
}
