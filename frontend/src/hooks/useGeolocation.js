import { useCallback, useEffect, useState } from 'react';
import { DEFAULT_COORDS } from '../lib/constants';

const TIMEOUT_MS = 8000;

/**
 * Best-effort browser geolocation, falling back to a known origin.
 *
 * `fallback` is true whenever the returned coordinates are the default rather
 * than a real fix, so the UI can say so instead of implying it knows where the
 * user is.
 */
export function useGeolocation({ auto = true } = {}) {
  const [state, setState] = useState({
    coords: DEFAULT_COORDS,
    fallback: true,
    loading: auto,
    denied: false,
  });

  const locate = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setState({ coords: DEFAULT_COORDS, fallback: true, loading: false, denied: true });
      return;
    }

    setState((current) => ({ ...current, loading: true }));
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setState({
          coords: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          },
          fallback: false,
          loading: false,
          denied: false,
        });
      },
      (error) => {
        setState({
          coords: DEFAULT_COORDS,
          fallback: true,
          loading: false,
          denied: error.code === error.PERMISSION_DENIED,
        });
      },
      { timeout: TIMEOUT_MS, maximumAge: 300000, enableHighAccuracy: false },
    );
  }, []);

  useEffect(() => {
    if (auto) locate();
  }, [auto, locate]);

  return { ...state, locate };
}
