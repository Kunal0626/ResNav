# ResNav AI

**Disaster-relief resource intelligence.** Describe a need in plain language and
ResNav finds the nearest relief centre that can actually meet it — then forecasts
when that centre will run out, scores which zones are most at risk, and plans the
allocation.

Built as a Flask JSON API and a React single-page app, deployable independently.

---

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Folder structure](#folder-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [Testing and quality](#testing-and-quality)
- [Deployment](#deployment)
- [Technology stack](#technology-stack)
- [Screenshots](#screenshots)
- [Future improvements](#future-improvements)

---

## Overview

Relief coordination fails in two predictable ways: the right supplies sit in the
wrong warehouse, and nobody notices a stockout until it happens. ResNav attacks
both.

A field coordinator types *"we urgently need 500 water packets for a flooded
village"*. ResNav classifies the intent, extracts the quantity and the urgency,
and ranks every relief centre by a weighted blend of semantic match, stock on
hand, proximity and urgency — showing its reasoning for each result rather than
an opaque score.

Behind that, the platform runs eight analytical modules over the same data:
depletion forecasting, zone risk prediction, anomaly detection, Monte Carlo
scenario simulation, natural-language querying, provider recommendation,
insight generation and semantic classification.

**Every figure in the interface is derived from the database.** Where the data
cannot support a claim — too little stock history to forecast, no requests to
score a zone against — the interface says so and shows an empty state instead of
filling the gap.

---

## Features

### Search and discovery
- **Semantic search** over relief centres — intent classification, quantity and
  urgency extraction, no keyword matching.
- **Explainable ranking**: `0.4 × semantic + 0.3 × stock + 0.2 × proximity +
  0.1 × urgency`, with a per-result breakdown of why it placed where it did.
- **Location-aware** with an honest fallback: when the browser cannot geolocate,
  the UI says it is ranking from Delhi rather than pretending otherwise.
- Embedded route preview and emergency helplines on the results page.

### Operations
- **Resource requests** from disaster zones, queued by a computed priority score
  (`severity × population × urgency ÷ available stock`).
- **AI allocation planning** — recommends a single supplier or a multi-centre
  split, with coverage and confidence.
- **Atomic dispatch**: stock deduction, allocation records, status transition and
  audit entry all commit together or not at all. Oversell is blocked at the SQL
  level.
- **Live stock** with safety thresholds and low-stock filtering.
- **Allocation history** and an append-only **audit log**.

### Intelligence
| Module | What it does |
| --- | --- |
| Command Center | Consolidated forecasts, risks, anomalies and insights |
| Depletion Forecast | Burn rate and days of cover per provider–resource line |
| Zone Risk Prediction | Weighted scoring on demand, severity, population, unmet supply |
| Recommendation Engine | Ranks suppliers on coverage, reliability, locality, urgency |
| Simulation Lab | Monte Carlo demand modelling per disaster scenario |
| NLP Console | Request parsing and natural-language querying of live data |
| Anomaly Detection | Isolation Forest over provider performance and stock movement |
| Insight Feed | Severity-tagged observations synthesised from the above |

### Interface
Warm sand light theme and a minimal greyscale dark theme, both following the OS
preference on first visit. Skeleton loading states, purposeful empty states,
error boundaries that isolate a failure to one panel, keyboard-reachable
controls with visible focus, `prefers-reduced-motion` support, and layouts that
work from 360 px upward.

---

## Architecture

```
┌───────────────────────────────┐        ┌────────────────────────────────┐
│  frontend/  React SPA         │        │  backend/  Flask JSON API      │
│                               │        │                                │
│  pages ──▶ hooks ──▶ lib/api ─┼── HTTP ┼─▶ api/ (blueprints)            │
│    │         │                │  JSON  │      │                         │
│    ▼         ▼                │        │      ▼                         │
│  components  contexts         │        │   services/  ──▶  ai/          │
│  (ui, charts, map)            │        │      │          (8 modules)    │
│                               │        │      ▼                         │
│  Vercel / Netlify / CF Pages  │        │   db/ ──▶ SQLite (WAL)         │
└───────────────────────────────┘        │                                │
                                         │  Render / Fly.io / Docker      │
                                         └────────────────────────────────┘
```

**Request flow.** A page calls a hook, the hook calls `lib/api.js`, which hits a
blueprint. The blueprint validates input, pulls what it needs from `db/queries.py`,
hands plain dictionaries to a service or AI module, and returns JSON. The AI
modules never touch the database, which is what makes them unit-testable.

**Design decisions worth knowing:**

- **One connection per request**, opened lazily on `flask.g` and closed on
  teardown. Writes run inside an explicit `transaction()` context manager.
- **SQLite in WAL mode.** The dataset is small and read-heavy; a separate
  database server would be operational overhead with no benefit. The schema uses
  foreign keys, check constraints and indexes throughout, so migrating to
  PostgreSQL later is mostly a driver change.
- **Pluggable text encoder.** Semantic search runs on TF-IDF (word + character
  n-grams, SVD-reduced) by default. Set `ENABLE_TRANSFORMERS=true` to use
  `all-MiniLM-L6-v2` instead. The transformer path is opt-in because torch is
  ~2.5 GB and does not fit most free deployment tiers — and ranking should
  degrade, not fail, when it is absent.
- **Uniform error envelope.** Every failure returns
  `{"error": {"code", "message", "details"}}`. Tracebacks are logged, never
  serialised to a client.
- **Secrets stay server-side.** The Google Maps key is used to build the embed
  URL on the backend and is never sent to the browser as a value.

---

## Folder structure

```
RESOURCE NAVIGATOR/
├── backend/
│   ├── app/
│   │   ├── api/              # Blueprints: health, overview, search,
│   │   │                     #   intelligence, inventory, ai_modules
│   │   ├── core/             # config, errors, logging, validation
│   │   ├── db/               # connection, queries, schema.sql, seed, bootstrap
│   │   ├── services/         # search, allocation, analytics, nlp, embeddings, geo
│   │   ├── ai/               # 8 standalone AI modules (pure functions)
│   │   └── __init__.py       # create_app() factory
│   ├── tests/                # pytest suite
│   ├── manage.py             # dev server, seed, health check
│   ├── wsgi.py               # gunicorn entry point
│   ├── Dockerfile, fly.toml, render.yaml, Procfile
│   └── requirements*.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/            # One component per route
│   │   ├── components/       # ui/ primitives, charts/, layout/, domain widgets
│   │   ├── hooks/            # useApi, useAction, useGeolocation, useMediaQuery
│   │   ├── contexts/         # ThemeContext, ToastContext
│   │   └── lib/              # api client, formatters, constants
│   ├── styles/               # resnav.css (design tokens), app.css (shell)
│   ├── public/               # favicon, robots.txt, _redirects, _headers
│   ├── vercel.json, netlify.toml
│   └── package.json
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

Each half has its own README with deeper detail:
[`backend/README.md`](backend/README.md) · [`frontend/README.md`](frontend/README.md)

---

## Getting started

**Prerequisites:** Python 3.11+, Node 20+.

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py seed          # creates and seeds instance/resource_navigator.db
python manage.py run           # http://127.0.0.1:5001
```

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local     # leave VITE_API_BASE_URL empty for local dev
npm run dev                    # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:5001`, so both halves are
same-origin locally and CORS never comes into play.

### Verify

```bash
curl http://127.0.0.1:5001/api/ready
```

---

## Environment variables

### `backend/.env`

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `APP_ENV` | no | `development` | `production` enables strict config checks and JSON logging |
| `SECRET_KEY` | **in production** | — | Session signing. Boot fails without it when `APP_ENV=production` |
| `CORS_ORIGINS` | **in production** | localhost:5173 | Comma-separated allowed frontend origins |
| `DATABASE_PATH` | no | `backend/instance/…` | Must point at a persistent volume in containers |
| `GOOGLE_MAPS_API_KEY` | no | — | Server-side only; enables the route preview |
| `ENABLE_TRANSFORMERS` | no | `false` | Opt in to sentence-transformers ranking |
| `GEO_SCALE_KM` | no | `10.0` | Distance at which the proximity score decays to ~0.37 |
| `MAX_RESULTS` | no | `15` | Search result cap |
| `LOG_LEVEL` | no | `INFO` | Standard Python log levels |

### `frontend/.env.local`

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | in production | Backend origin, no trailing slash. Empty locally to use the dev proxy |

> **Anything prefixed `VITE_` is compiled into the JavaScript bundle and is
> publicly readable.** Never put a secret in the frontend environment.

---

## Testing and quality

```bash
# Backend
cd backend
python -m pytest                    # 51 tests
python -m pytest --cov=app          # with coverage
python -m ruff check .              # lint

# Frontend
cd frontend
npm run lint
npm run build
```

The backend suite covers the endpoint contract, the full request → recommend →
allocate → conflict lifecycle, oversell rejection and rollback, search ranking
and validation, encoder fallback, and the production configuration guardrails.

---

## Deployment

The two halves deploy independently. Deploy the backend first — the frontend
needs its URL.

### Backend

<details>
<summary><b>Render</b></summary>

`render.yaml` is committed. Create a Blueprint instance from the repository,
then set `CORS_ORIGINS` to your frontend origin. The blueprint provisions a 1 GB
disk at `/var/data`, which SQLite requires — without a persistent disk the
database is recreated empty on every deploy.
</details>

<details>
<summary><b>Fly.io</b></summary>

```bash
cd backend
fly launch --no-deploy
fly volumes create resnav_data --size 1 --region bom
fly secrets set SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
fly secrets set CORS_ORIGINS=https://your-frontend.vercel.app
fly deploy
```
</details>

<details>
<summary><b>Railway</b></summary>

Set the root directory to `backend`. Railway detects the `Procfile`. Add a
volume mounted at `/data` and set `DATABASE_PATH=/data/resource_navigator.db`,
plus `APP_ENV`, `SECRET_KEY` and `CORS_ORIGINS`.
</details>

<details>
<summary><b>Docker / DigitalOcean</b></summary>

```bash
cd backend
docker build -t resnav-api .
docker run -p 8000:8000 \
  -e APP_ENV=production \
  -e SECRET_KEY="$(openssl rand -base64 36)" \
  -e CORS_ORIGINS=https://your-frontend.example \
  -v resnav-data:/data \
  resnav-api
```
</details>

### Frontend

<details>
<summary><b>Vercel</b></summary>

Import the repository, set the root directory to `frontend`. `vercel.json`
supplies the build command, SPA rewrites, cache and security headers. Add
`VITE_API_BASE_URL` pointing at the deployed backend.
</details>

<details>
<summary><b>Netlify</b></summary>

`netlify.toml` configures base, build, publish and redirects. Add
`VITE_API_BASE_URL` in the site environment.
</details>

<details>
<summary><b>Cloudflare Pages</b></summary>

Build command `npm run build`, output directory `dist`, root directory
`frontend`. `public/_redirects` and `public/_headers` are copied into the build.
</details>

### After deploying

1. Set `CORS_ORIGINS` on the backend to the frontend's exact origin — the API
   rejects everything else.
2. Confirm `https://your-api/api/ready` returns `{"status": "ready"}`.
3. Restrict the Google Maps key by HTTP referrer, if you configured one.

### Both halves locally, production-parity

```bash
cd frontend && npm run build && cd ..
SECRET_KEY=$(openssl rand -base64 36) docker compose up --build
# frontend http://localhost:8080 · api http://localhost:8000
```

---

## Technology stack

**Backend** — Python 3.11+ · Flask 3 · SQLite (WAL) · scikit-learn · NumPy ·
gunicorn · pytest · ruff · optional sentence-transformers

**Frontend** — React 18 · Vite 5 · React Router 6 · Tailwind CSS 3 · Chart.js 4 ·
Leaflet 1.9 · ESLint · Prettier

**Why these** — Flask because the API surface is small and explicit SQL suits a
schema this shaped better than an ORM. SQLite because the dataset is small and
read-heavy. Vite because the build is a second and the dev proxy removes CORS
from local development. No component library: the project already had a design
system in `resnav.css`, and the goal was to preserve it, not replace it.

---

## Screenshots

> Add captures to `docs/screenshots/` and reference them here.

| Screen | Path |
| --- | --- |
| Overview — KPIs, relief network map, insight feed | `docs/screenshots/overview.png` |
| Search results — explainable ranking | `docs/screenshots/results.png` |
| Command Center — forecasts, risk, anomalies | `docs/screenshots/command-center.png` |
| Resource Requests — allocation planning dialog | `docs/screenshots/requests.png` |
| Depletion Forecast — burn rates and runway | `docs/screenshots/forecast.png` |
| Light theme | `docs/screenshots/light-theme.png` |

---

## Future improvements

**Data and scale**
- PostgreSQL adapter behind the existing query layer, for multi-instance deploys.
- Persist embeddings so the vector index survives a restart instead of being
  rebuilt on first search.
- Replace the zone `state` proximity heuristic with real zone coordinates and
  haversine distance, which the schema does not currently carry.

**Product**
- Authentication and per-role permissions — the API is currently unauthenticated
  and every caller can allocate.
- Optimistic UI for allocation, with rollback on conflict.
- Live updates via server-sent events instead of manual refresh.
- Partial and reversible allocations (return stock to a centre).

**Engineering**
- Frontend component tests (Vitest + Testing Library).
- OpenAPI specification generated from the blueprints.
- Rate limiting on the write endpoints.
- CI running both suites, plus a Lighthouse budget on the built frontend.
