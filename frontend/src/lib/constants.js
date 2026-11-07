/** Central Delhi — the ranking origin when the browser cannot geolocate. */
export const DEFAULT_COORDS = { latitude: 28.6139, longitude: 77.209 };

export const SEVERITY_TONE = {
  Critical: 'red',
  High: 'orange',
  Medium: 'amber',
  Low: 'emerald',
  Warning: 'amber',
  Stable: 'emerald',
};

export const STATUS_TONE = {
  pending: 'amber',
  allocated: 'blue',
  fulfilled: 'emerald',
  rejected: 'slate',
  critical: 'red',
  warning: 'amber',
  info: 'indigo',
};

export const SCENARIOS = [
  { value: 'flood', label: 'Flood' },
  { value: 'cyclone', label: 'Cyclone' },
  { value: 'earthquake', label: 'Earthquake' },
  { value: 'drought', label: 'Drought' },
  { value: 'heatwave', label: 'Heatwave' },
];
