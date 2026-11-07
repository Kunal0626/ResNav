# Audit of ResNav AI, before the merge

Phase 0 deliverable. Everything here was measured on 2026-11-07, not inferred
from reading the code. Where something was not measured, it says so.

The point of this document is that the merged project should inherit ResNav's
working code and *not* its unverified claims. Phase 9 rewrites the README; this
file is the evidence that decides what that README is allowed to say.

## Method

A source-only copy of `~/Downloads/work/projects/RESOURCE NAVIGATOR` was made in
a scratch directory — no `node_modules`, no `.venv`, no `dist`, no database
file — and then built from nothing: a fresh virtualenv, a fresh `npm install`,
`manage.py seed`, both test suites, both dev servers. That is the "can a
stranger clone this and run it" test. The source project was not modified.

**Machine and versions.** Apple Silicon Mac (arm64, T8122), macOS 26.6.2 build
25G83, Darwin 25.6.0. Python 3.14.6, Node v22.19.0, npm 10.9.3.
MySQL 9.5.0 server running locally. Resolved Python dependencies: Flask 3.1.3,
numpy 2.5.4, scikit-learn 1.9.1, scipy 1.18.1, pytest 9.2.0, ruff 0.17.4.
Docker is **not** installed.

## Does it build and run from scratch?

| Step | Result |
|---|---|
| `python3 -m venv` + `pip install -r requirements-dev.txt` | works, exit 0 |
| `python manage.py seed` | works, creates a 315 KB database |
| `python -m pytest` | **51 passed** — but see "Broken test isolation" |
| `python -m ruff check .` | All checks passed |
| `npm install` + `npm run lint` | clean at `--max-warnings 0` |
| `npm run build` | works, 1.25 s, largest chunk 182 kB (63 kB gzip) |
| `npm audit` | reports high and moderate vulnerabilities. **Not yet triaged.** |

Test counts by file: `test_api.py` 23, `test_search.py` 15,
`test_allocation.py` 8, `test_config.py` 5.

## What the old README claimed, and whether it is true

### True, verified

| Claim | Evidence |
|---|---|
| "51 tests" | exactly 51, all passing |
| Ranking is `0.4·semantic + 0.3·stock + 0.2·proximity + 0.1·urgency` | `services/nlp_engine.py:31` defines exactly those four weights |
| Per-result reasoning, not an opaque score | live output: `AI Ranked: High stock, Close (0.0 km), Urgency boost [Sem: 0.07, Stock: 0.93, Dist: 1.00, Urg: 0.35]` |
| Atomic dispatch; oversell blocked at the SQL level | `queries.deduct_stock` issues `UPDATE … SET quantity = quantity - ? WHERE … AND quantity >= ?` and raises when `rowcount == 0`, inside a `BEGIN IMMEDIATE` transaction |
| Anomaly detection uses Isolation Forest | `IsolationForest(contamination=0.1, random_state=42)`, real scikit-learn |
| Monte Carlo scenario simulation | real, `np.random.RandomState(42)`, reports p50/p90/p95 |
| Depletion forecasting | real `LinearRegression` over stock history |
| TF-IDF word + character n-grams, SVD-reduced | word `(1,2)`, `char_wb (3,5)`, `TruncatedSVD`, as described |
| Transformer path is opt-in | `ENABLE_TRANSFORMERS`, `SentenceTransformer` imported lazily |
| Honest empty states and a stated Delhi fallback | the UI prints `Low confidence (19%). Closest: Emergency.` rather than inventing an answer |
| Google Maps key stays server-side | `/api/navigation-events` returns a built URL; the key never reaches the bundle |

**API surface.** 26 routes are registered; 22 were probed and 21 returned 200.
The one failure was a malformed probe body on `/api/navigation-events`, which
returns 200 once given `latitude` and `longitude`. No broken endpoint was found.

**Frontend.** All 15 routes render with no console errors and no error-boundary
crashes: `/`, `results`, `command-center`, `insights`, `forecast`, `risk`,
`recommend`, `simulation`, `nlp`, `anomaly`, `explorer`, `requests`, `stock`,
`allocations`, `logs`.

**Allocation lifecycle,** run live against the API:

```
create request      -> 201  priority=1041.6667  status=pending
recommendation      -> 200  split_allocation, 3 legs, 75% coverage
allocate            -> 200  status=allocated  allocated=30.0  ids=[8,9,10]
allocate again      -> 409  conflict
oversell (999999)   -> 409  conflict, coverage 0%, shortage 999999
negative stock rows afterwards: 0
audit log grew 32 -> 41
```

Partial fulfilment behaves correctly: 40 requested, 30 available, status stayed
`allocated` rather than `fulfilled`.

### Overstated, or not what it sounds like

1. **Semantic search contributes almost nothing on the README's own example.**
   For *"we urgently need 500 water packets for a flooded village"* the intent
   classifies as `unknown` at 18.6% confidence and the breakdown reads
   `Sem: 0.07` against `Dist: 1.00`. The top result is a community kitchen in
   Delhi, placed there by proximity and stock. Quantity (500) and urgency
   (1.35×) *are* extracted correctly. So the feature is wired up, weighted and
   explainable — but "no keyword matching" oversells the quality of the signal.
   Either tune it and measure the change, or describe it as hybrid ranking.
2. **"Every figure is derived from the database"** is true, but the database is
   small: 18 providers, 5 resources, 5 zones, 29 stock rows, 3 seeded requests.
   Forecasts and anomaly scores run on very little history.
3. **The screenshots section points at files that do not exist.**
4. **The entire deployment section is unverified.** `render.yaml`, `fly.toml`,
   `Procfile`, `Dockerfile` and `docker-compose.yml` are committed and
   plausible; nothing has ever been deployed and Docker is not installed here.

## Defects found

### Broken test isolation — the most serious one

`tests/conftest.py` says *"Every test runs against a fresh, seeded temporary
database"* and builds one per test with `tmp_path`. It does not work.

`db/connection.py:connect()` resolves its path from the **`lru_cache`d global**
`get_settings()`, not from the `Settings` object the test injected into
`create_app`. `app.config["SETTINGS"]` is written but never read by the data
layer. So every request inside a test opens
`backend/instance/resource_navigator.db` — the developer's real database.

Measured proof: with that file deleted, all of `test_allocation.py` errors with
`sqlite3.OperationalError: no such table: Resources`. Recreate it, and the suite
passes. Running `test_allocation.py` grew the real database's `Requests` table
from **11 rows to 19**.

**The suite is therefore not idempotent.** Run against one database repeatedly,
it passes twice and then fails from the third run onward:

```
run 1: total stock 2505, Requests 11 rows   51 passed
run 2: total stock 2460, Requests 19 rows   51 passed
run 3: total stock 2430, Requests 27 rows   FAILED test_partial_plan_leaves_request_allocated_not_fulfilled
run 4: total stock 2430, Requests 35 rows   FAILED (same)
```

Each run drains stock and adds eight `Requests` rows. Once the allocation tests
have exhausted the stock they draw on, the partial-fulfilment test can no longer
produce a partial result and fails. Nothing about the code changed between run 2
and run 3 — only the accumulated state of a database the tests were never
supposed to touch.

Consequences: results depend on how many times the suite has been run before,
on whether a seeded dev database happens to exist, and on test order. A green
run proves less than it appears to.

The fix is for the connection layer to resolve its path from the active
application's settings rather than a cached global. It lands in Phase 4
alongside the MySQL port, with a test that asserts isolation — deleting no
database and still passing twice in a row. Until then `./run.sh test` deletes
and re-seeds `backend/instance` on every run, which makes the target
reproducible without pretending the bug is fixed.

### `backend/.env` is never read

The old README tells you to `cp .env.example .env`. Nothing loads it — there is
no `python-dotenv` dependency and no loader anywhere in the backend. `Settings`
reads `os.environ` only, so a local `.env` had no effect whatsoever.

Fixed in this phase: there is now one `.env` at the repo root, and `run.sh`
parses it and **exports** every key before starting anything, so the file
actually takes effect.

### Duplicated NLP logic

`app/ai/nlp_engine.py` (298 lines) and `app/services/nlp_engine.py` (456 lines)
both implement quantity extraction and urgency scoring. Only the `ai/` one is
re-exported by `ai/__init__.py`. To be resolved during the port.

## SQLite constructs that have to be ported

| # | Construct | Where | MySQL replacement |
|---|---|---|---|
| 1 | `PRAGMA` ×6 — `foreign_keys`, `journal_mode=WAL`, `synchronous`, `temp_store`, `cache_size`, `busy_timeout` | `connection.py:23-32`, `schema.sql:11-12`, `seed.py:415`, `health.py:39` | mostly unnecessary; InnoDB does this. `busy_timeout` → `innodb_lock_wait_timeout` |
| 2 | `datetime('now')` ×19 in the schema, ×7 in Python | `schema.sql`, `queries.py`, `seed.py`, `forecast_engine.py` | `CURRENT_TIMESTAMP` / `NOW(6)` |
| 3 | `AUTOINCREMENT` ×18 | `schema.sql` | `AUTO_INCREMENT` |
| 4 | `INSERT OR IGNORE` ×9, `INSERT OR REPLACE` ×2 | `seed.py`, `schema.sql:453,487` | `INSERT IGNORE`, `INSERT … ON DUPLICATE KEY UPDATE` |
| 5 | `RAISE(ABORT, …)` | `schema.sql:405` | `SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = …` |
| 6 | `sqlite3.Row` row factory, `lastrowid` ×2, `sqlite_master` ×2 | `connection.py`, `queries.py`, `health.py` | `DictCursor`; `lastrowid` survives; `information_schema` |
| 7 | **`BEGIN IMMEDIATE`** | `connection.py:68` | see below |
| 8 | `TEXT` timestamps, `REAL` quantities, `INTEGER` booleans | throughout | `DATETIME(6)`, `DECIMAL(12,3)`, `TINYINT(1)` |
| 9 | Trigger bodies using `INSERT OR REPLACE` and correlated subqueries | triggers 4 and 5 | rewrite; mind MySQL's rule that a trigger may not modify its own table |

### Why `BEGIN IMMEDIATE` is the one that matters

`BEGIN IMMEDIATE` takes a **database-wide** write lock. In SQLite there is only
ever one writer, and that — more than the `WHERE quantity >= ?` clause — is what
actually makes the current oversell protection safe.

MySQL has row-level locking and many concurrent writers. The conditional
`UPDATE` stays atomic as a single statement, but the **read-then-decide** gap
between `recommend()` and `execute()` becomes a genuine race: two sessions can
both read the same balance, both build a plan against it, and both commit.

This is exactly why the allocation decision has to move into a stored procedure
that takes `SELECT … FOR UPDATE` locks in a fixed order. It also means Phase 6
can demonstrate a *real* bug and a *real* fix rather than a staged one.

## The target MySQL server

`./run.sh check` was run against the development server on 2026-11-07. All 15
probes pass. What it reported:

| Setting | Value |
|---|---|
| version | 9.5.0, MySQL Community Server - GPL |
| default_storage_engine | InnoDB |
| transaction_isolation | REPEATABLE-READ |
| innodb_lock_wait_timeout | 50 |
| innodb_deadlock_detect | ON |
| character_set / collation | utf8mb4 / utf8mb4_0900_ai_ci |
| sql_mode | `ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION` |
| log_bin | ON |
| lower_case_table_names | 2 |

Every feature the later phases depend on is confirmed on this server rather
than assumed: enforced `CHECK` constraints (rejecting with errno 3819),
`SIGNAL SQLSTATE '45000'` from a trigger (errno 1644, message preserved
verbatim), `STORED` generated columns, the `NULL`-in-a-unique-index trick that
substitutes for a partial index, composite foreign keys (errno 1452 on a
mismatched pair), `ON DELETE CASCADE` blocked by a downstream `RESTRICT`
(errno 1451), window functions, recursive CTEs, `ROLLUP`,
`SELECT ... FOR UPDATE`, a no-op `ON DUPLICATE KEY UPDATE` upsert, and
creating a `DETERMINISTIC` function.

Two things the probe found that had to be fixed before Phase 3 could start:

1. **Binary logging is on and `log_bin_trust_function_creators` was off**, so a
   non-`SUPER` account could not create triggers or stored functions at all
   (error 1419). The probe caught this in the most useful possible way: the
   trigger silently failed to be created, so the `INSERT` that should have
   been rejected *succeeded*, and `trigger_signal_45000` reported
   `errno=0 sqlstate= msg=""`. A test that expects an error and gets silence
   is a failing test. Resolved with
   `SET PERSIST log_bin_trust_function_creators = 1`, now recorded as a
   prerequisite in the README.
2. **The probe originally created its own scratch database**, which required
   `CREATE`/`DROP` on `*.*` — a global privilege a project account should not
   hold. It now creates `probe_`-prefixed objects inside the project database
   and drops them, so `GRANT ALL ON resnav.*` is sufficient. Verified
   afterwards: `resnav` contains 0 tables, 0 routines and 0 triggers.

`sql_mode` includes `STRICT_TRANS_TABLES` and `ONLY_FULL_GROUP_BY`, which the
Phase 3 DDL and the Phase 6 reporting queries both have to satisfy — a silent
truncation will be an error here, and every non-aggregated column has to
appear in `GROUP BY`. `lower_case_table_names = 2` means table names are
stored as written but compared case-insensitively, which is macOS's default
and differs from a typical Linux server's `0`; the schema therefore should not
rely on two tables whose names differ only by case.

## Inherited schema, as a starting point

ResNav's `schema.sql` is 667 lines: **17 tables, 5 triggers, 12 views, 40
indexes**. Seeded row counts after `manage.py seed`:

```
Providers 18   Resources 5   Zones 5   Requests 3   StockLevels 29
ServicesOffered 29   RiskScores 29   ResourceConsumptionRate 29
StockThresholds 5   ServiceCategory 8   EmergencyContact 6   ZoneSummary 3
Allocations 0   AllocationHistory 0   AuditLog 0   StockHistory 0
SystemLog 0   UserQuery 0
```

Six of the twelve views are backward-compatibility shims mapping old names onto
new tables (`ResourceType`, `ServiceProvider`, `Location`, `ResourceStock`,
`ResourceRequest`, `Allocation`). Whether those survive the merge is a Phase 2
decision.

## Secrets and git hygiene

Clean, with nothing to remediate.

- No real `.env` anywhere in the source project — only two `.env.example` files.
- No key-shaped strings (`AIza…`, `sk-…`, `ghp_…`, inline `SECRET_KEY`) in any
  backend or frontend source file.
- Two `resource_navigator.db` files exist on disk (475 KB, 463 KB); both match
  ignore rules and neither was imported.
- ResNav had **no git repository**, so nothing was ever committed from it.
