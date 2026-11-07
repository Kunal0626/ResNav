import { useEffect, useRef } from 'react';
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from 'chart.js';
import { useTheme } from '../../contexts/ThemeContext';

// Registering only what is used keeps the charts chunk small; the original
// pulled the entire Chart.js UMD bundle from a CDN on every page.
ChartJS.register(
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  DoughnutController,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
);

export const PALETTE = [
  '#6366f1',
  '#8b5cf6',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#f43f5e',
  '#3b82f6',
  '#14b8a6',
];

/**
 * Thin declarative wrapper. Rebuilds the chart when the theme changes so axis
 * and grid colours track light/dark instead of staying stuck at first render.
 */
export function Chart({ type, data, options, height = 260, ariaLabel }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const dark = theme === 'dark';
    const grid = dark ? 'rgba(255,255,255,0.06)' : 'rgba(44,40,37,0.07)';
    const text = dark ? '#999999' : '#6B6560';

    const base = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: false,
          labels: { color: text, font: { family: 'Inter', size: 11 }, boxWidth: 10 },
        },
        tooltip: {
          backgroundColor: dark ? '#1A1A1A' : '#FDFCF9',
          titleColor: dark ? '#E8E8E8' : '#2C2825',
          bodyColor: text,
          borderColor: dark ? '#2C2C2C' : '#E8E3DA',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          displayColors: true,
          titleFont: { family: 'Inter', size: 12, weight: '600' },
          bodyFont: { family: 'Inter', size: 11 },
        },
      },
      scales:
        type === 'doughnut' || type === 'pie'
          ? undefined
          : {
              x: {
                grid: { color: grid, drawBorder: false },
                ticks: { color: text, font: { family: 'Inter', size: 10 }, maxRotation: 0 },
              },
              y: {
                beginAtZero: true,
                grid: { color: grid, drawBorder: false },
                ticks: { color: text, font: { family: 'Inter', size: 10 } },
              },
            },
    };

    chartRef.current = new ChartJS(canvas, {
      type,
      data,
      options: mergeDeep(base, options ?? {}),
    });

    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [type, data, options, theme]);

  return (
    <div style={{ height }} className="relative w-full">
      <canvas ref={canvasRef} role="img" aria-label={ariaLabel} />
    </div>
  );
}

function mergeDeep(target, source) {
  const output = { ...target };
  for (const [key, value] of Object.entries(source)) {
    output[key] =
      value && typeof value === 'object' && !Array.isArray(value) && target[key]
        ? mergeDeep(target[key], value)
        : value;
  }
  return output;
}
