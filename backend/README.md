# ResNav API

Flask JSON API for the ResNav relief-resource platform. Serves search, inventory
operations and eight analytical modules. No templates — the frontend is a
separate deployable.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py seed
python manage.py run          # http://127.0.0.1:5001
```

## Commands

| Command | Purpose |
| --- | --- |
| `python manage.py run` | Development server. Binds to `127.0.0.1` by default |
| `python manage.py run --host 0.0.0.0 --reload` | Expose on the LAN, with auto-reload |
| `python manage.py seed` | Create or migrate the database |
| `python manage.py check` | Readiness diagnostics: connection, schema, foreign keys |
| `python -m pytest` | Test suite |
| `python -m ruff check .` | Lint |
| `gunicorn --config gunicorn.conf.py wsgi:app` | Production server |

`manage.py run` refuses to start when `APP_ENV=production` — use gunicorn there.

## Layout

```
app/
├── __init__.py       create_app() factory, CORS, security headers, teardown
├── core/
│   ├── config.py     Settings dataclass; fails fast on missing prod config
│   ├── errors.py     ApiError hierarchy and the uniform error envelope
│   ├── logging.py    Human-readable in dev, JSON lines in production
│   └── validation.py Input coercion helpers that raise 422s
├── db/
│   ├── connection.py Per-request connection, PRAGMAs, transaction()
│   ├── queries.py    All SQL, grouped by domain
│   ├── schema.sql    18 tables, 6 views, indexes, constraints
│   ├── seed.py       Idempotent schema + reference data
│   └── bootstrap.py  ensure_database(), called from the factory
├── services/
│   ├── search_service.py  Search orchestration
│   ├── nlp_engine.py      Intent classification and hybrid ranking
│   ├── embeddings.py      Pluggable encoder (TF-IDF | transformers)
│   ├── allocation.py      Recommend and commit allocations
│   ├── analytics.py       Insights, heatmap, system status
│   └── geo.py             Haversine, Maps URL construction
├── ai/                    8 pure-function modules, no DB access
└── api/                   Blueprints
```

## Endpoints

All routes are prefixed `/api`.

### Health
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Liveness. Does not touch the database |
| GET | `/ready` | Readiness: connection, core tables, foreign-key integrity |

### Overview and search
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/overview` | KPIs, providers, activity, heatmap, insights, ticker |
| GET | `/reference` | Resources, zones, emergency contacts |
| POST | `/search` | Semantic search. Body: `query`, `latitude`, `longitude`, `limit` |
| POST | `/navigation-events` | Records a click, returns the Maps deep link |

### Intelligence
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard` | Forecasts, zone risks, anomalies, insights |
| GET | `/forecast` | Per-line burn rate, runway, risk score |
| GET | `/forecast/series` | Daily stock totals with a projection |
| GET | `/explorer` | Read-only table dump with chart aggregates |

### Inventory
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/stock` | Stock levels. `?low=1` filters to below-threshold |
| GET | `/requests` | Request queue. `?status=`, `?limit=` |
| POST | `/requests` | Create a request; computes the priority score |
| GET | `/requests/<id>/recommendation` | Allocation plan. Read-only |
| POST | `/requests/<id>/allocate` | Commit an allocation, atomically |
| POST | `/requests/<id>/status` | Transition a request's status |
| GET | `/allocations` | Dispatch history |
| GET | `/logs` | Audit trail |

### AI modules
Prefixed `/api/ai`: `nlp-understand`, `recommend-provider`, `forecast`,
`risk-predict`, `anomaly-detect`, `query`, `simulate`, `insights`.

## Error format

Every failure returns the same envelope, with an appropriate status:

```json
{ "error": { "code": "validation_error", "message": "'query' is required and must be a non-empty string.", "details": { "field": "query" } } }
```

| Status | Code | Meaning |
| --- | --- | --- |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Business rule violated (already allocated, insufficient stock) |
| 422 | `validation_error` | Malformed or out-of-range input |
| 500 | `internal_error` | Unexpected. Logged with a traceback, never returned with one |

## Semantic search

Ranking is `0.4 × semantic + 0.3 × stock + 0.2 × proximity + 0.1 × urgency`, and
every result carries a `why` string explaining its placement.

The encoder is pluggable:

- **TF-IDF (default)** — word + character n-grams, SVD-reduced to 128 dimensions.
  Character n-grams handle the typos and transliterations ("paani", "medcine")
  that field queries are full of. No extra dependencies.
- **sentence-transformers** — set `ENABLE_TRANSFORMERS=true` and install
  `requirements-ml.txt` for `all-MiniLM-L6-v2`. Better ranking, but torch adds
  ~2.5 GB and will not fit most free tiers.

If transformers are requested but unavailable, the service logs a warning and
falls back to TF-IDF rather than failing the request.

## Database

SQLite in WAL mode: foreign keys on, `synchronous=NORMAL`, 64 MB page cache,
5-second busy timeout. Connections are per-request and closed on teardown.

Writes go through `transaction()`, which issues `BEGIN IMMEDIATE` and rolls back
on any exception. Stock deduction guards against oversell in the `UPDATE`
itself — `WHERE quantity >= ?` — so two concurrent allocations cannot both read
the same balance and both succeed.

**In a container, set `DATABASE_PATH` to a mounted volume.** Without one the
database lives in the container filesystem and is lost on every restart.

## Configuration

See `.env.example`. `APP_ENV=production` makes `SECRET_KEY` and `CORS_ORIGINS`
mandatory — the app raises `ConfigError` at import rather than starting with an
insecure default. This is deliberate: the previous version shipped a hardcoded
fallback secret.

## Tests

```bash
python -m pytest              # 51 tests
python -m pytest --cov=app
```

Each test runs against a fresh copy of a seeded temporary database, so mutating
tests cannot affect one another.
