import { useEffect, useRef } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { EmptyState } from './ui';

/**
 * Leaflet map of relief centres with a risk overlay.
 *
 * Leaflet is imported dynamically so its ~150 KB only loads on screens that
 * actually show a map — it used to be a blocking CDN tag in the global layout.
 */
export function RiskMap({ providers = [], heatmap = [], height = 380 }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container || (!providers.length && !heatmap.length)) return undefined;

    (async () => {
      const L = (await import('leaflet')).default;
      await import('leaflet/dist/leaflet.css');
      if (cancelled || !containerRef.current) return;

      const map = L.map(container, {
        scrollWheelZoom: false, // Trapping page scroll inside a map is hostile.
        attributionControl: true,
        zoomControl: true,
      });
      mapRef.current = map;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 18,
      }).addTo(map);

      const bounds = [];

      for (const zone of heatmap) {
        if (zone.lat == null || zone.lon == null) continue;
        const intensity = Number(zone.risk_intensity) || 0;
        L.circle([zone.lat, zone.lon], {
          // Radius scales with risk so hotter areas read as larger.
          radius: 24000 + intensity * 46000,
          color: intensity > 0.66 ? '#ef4444' : intensity > 0.33 ? '#f59e0b' : '#10b981',
          fillColor: intensity > 0.66 ? '#ef4444' : intensity > 0.33 ? '#f59e0b' : '#10b981',
          fillOpacity: 0.12,
          weight: 1,
        })
          .addTo(map)
          .bindPopup(
            `<strong>${escapeHtml(zone.city ?? 'Zone')}</strong><br/>Risk index ${(intensity * 100).toFixed(0)}%`,
          );
      }

      for (const provider of providers) {
        if (provider.latitude == null || provider.longitude == null) continue;
        bounds.push([provider.latitude, provider.longitude]);
        L.circleMarker([provider.latitude, provider.longitude], {
          radius: 6,
          color: '#6366f1',
          fillColor: '#6366f1',
          fillOpacity: 0.85,
          weight: 2,
        })
          .addTo(map)
          .bindPopup(
            `<strong>${escapeHtml(provider.name)}</strong><br/>` +
              `${escapeHtml(provider.city ?? '')}<br/>` +
              `Stock: ${Number(provider.total_stock ?? 0).toLocaleString('en-IN')} units`,
          );
      }

      if (bounds.length) {
        map.fitBounds(bounds, { padding: [36, 36], maxZoom: 7 });
      } else {
        map.setView([22.5, 79], 4);
      }

      // Leaflet mis-sizes itself inside a container that was laid out after init.
      requestAnimationFrame(() => map.invalidateSize());
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [providers, heatmap]);

  // Tile filtering for dark mode is handled in CSS; this only forces a repaint.
  useEffect(() => {
    mapRef.current?.invalidateSize();
  }, [theme]);

  if (!providers.length && !heatmap.length) {
    return (
      <EmptyState
        icon="location"
        title="No mapped locations"
        description="Relief centres will appear here once providers with coordinates are registered."
      />
    );
  }

  return (
    <div
      ref={containerRef}
      style={{ height }}
      className="w-full overflow-hidden rounded-xl"
      role="application"
      aria-label="Map of relief centres and zone risk"
    />
  );
}

function escapeHtml(value) {
  return String(value ?? '').replace(
    /[&<>"']/g,
    (char) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char],
  );
}
