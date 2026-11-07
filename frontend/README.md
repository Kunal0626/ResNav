# ResNav Frontend

React single-page app for the ResNav relief-resource platform. Talks to the
Flask API over JSON; deploys as static files to any CDN.

## Quick start

```bash
npm install
cp .env.example .env.local     # leave VITE_API_BASE_URL empty locally
npm run dev                    # http://localhost:5173
```

The dev server proxies `/api` to `http://127.0.0.1:5001`, so the backend appears
same-origin and CORS never enters local development. Start the backend first
(`cd ../backend && python manage.py run`).

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Dev server with hot module replacement |
| `npm run build` | Production build to `dist/` |
| `npm run preview` | Serve the built output locally |
| `npm run lint` | ESLint, zero warnings tolerated |
| `npm run format` | Prettier |

## Layout

```
src/
├── main.jsx              Entry: providers, router, style imports
├── App.jsx               Routes, lazy loading, legacy-path redirects
├── pages/                One component per route
├── components/
│   ├── layout/           AppShell, Sidebar, ToastViewport, ErrorBoundary
│   ├── ui/               Card, Button, Badge, Field, Table, Empty/Error
│   │                     states, Skeleton, Progress, Portal, Icon
│   ├── charts/           Chart.jsx — theme-aware Chart.js wrapper
│   ├── KpiCard.jsx       Stat tile with an optional real sparkline
│   ├── InsightList.jsx   Severity-tagged insight rendering
│   ├── RiskMap.jsx       Leaflet map, dynamically imported
│   └── Ticker.jsx        Status strip, pauses on hover and focus
├── hooks/
│   ├── useApi.js         useApi (fetch + cancel + retry), useAction
│   ├── useGeolocation.js Best-effort location with an honest fallback
│   ├── useDocumentTitle.js
│   └── useMediaQuery.js  useIsDesktop, usePrefersReducedMotion
├── contexts/
│   ├── ThemeContext.jsx  Light/dark, OS-following until the user chooses
│   └── ToastContext.jsx  Transient notifications
└── lib/
    ├── api.js            Typed API client with a uniform ApiError
    ├── format.js         Number, date, distance and relative-time formatters
    └── constants.js      Palettes, tone maps, scenario list

styles/
├── resnav.css            Design tokens and component classes
└── app.css               Tailwind layers plus the application shell
```

## Design system

The visual language is unchanged from the original: warm sand light theme,
minimal greyscale dark theme, indigo/violet accent, Inter, an 8 px spacing grid.

`styles/resnav.css` holds the tokens (`--rn-bg`, `--rn-text`, `--c-accent`, the
radius, shadow and transition scales) and the component classes (`dash-card`,
`rn-btn`, `rn-table`, `badge-*`). `styles/app.css` adds the shell — layout, glass
surfaces, navigation, motion.

**Extending it:** reach for an existing token before adding a colour, and an
existing `ui/` primitive before writing new markup. Tailwind utilities handle
layout and spacing; the tokens handle colour and elevation.

Theme is applied by an inline script in `index.html` before first paint, so the
page never flashes the wrong theme.

## Accessibility

Skip link to main content · visible focus rings on every interactive element ·
`aria-pressed` on toggle filters, `aria-busy` on loading regions, `role="alert"`
on errors · focus moves to `<main>` on navigation · Escape closes the mobile
drawer and modals · horizontal scroll containers are keyboard-reachable ·
`prefers-reduced-motion` disables the mesh background, ticker and transitions.

## Performance

Routes are code-split; Chart.js and Leaflet are separate chunks loaded only on
the pages that need them. Initial JS is roughly 65 KB gzipped. Chart.js
components are registered individually rather than importing the full bundle,
and Leaflet is dynamically imported inside `RiskMap`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Backend origin, no trailing slash. Empty locally to use the dev proxy |
| `VITE_DEV_API_PROXY` | Override the dev proxy target (default `http://127.0.0.1:5001`) |

> Everything prefixed `VITE_` is compiled into the bundle and publicly readable.
> Never put a secret here. The Google Maps key lives on the backend, which
> returns a fully formed embed URL.

## Deployment

`vercel.json`, `netlify.toml` and `public/_redirects` + `public/_headers` are all
committed. Each configures the SPA fallback (unknown paths serve `index.html`),
immutable caching for hashed assets, and security headers.

Set `VITE_API_BASE_URL` in the host's environment, and add the resulting origin
to the backend's `CORS_ORIGINS`.
