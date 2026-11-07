# ResNav

**Disaster-relief resource allocation, where the database is the source of truth.**

React SPA → Flask JSON API → MySQL 8. Relief centres hold stock; disaster zones
raise requests; the system ranks candidate centres by real distance and commits
an allocation atomically, with the constraints, triggers and stored procedures —
not the application code — guaranteeing that stock never goes negative and the
same unit is never promised twice. Eight analytical modules sit on top as pure
Python with no database access of their own.

> **Status: mid-build, and this README does not describe a finished product.**
> The repository currently holds a working SQLite-backed application (imported
> from an earlier project, ResNav AI) plus the design and tooling for the MySQL
> layer that will replace it. **The MySQL layer does not exist yet.** The
> roadmap below says exactly what is built and what is not.
>
> Nothing in this file is a claim about performance. There are no measured
> numbers here yet; when there are, they will come from a script in this repo
> and will record the machine and versions alongside them.

---

## Where this came from

Two projects merged into one:

- **ResNav AI** — a Flask + React application with semantic relief-centre
  search, explainable ranking, a request queue, allocation planning, eight
  analytics modules, atomic dispatch and an audit log, all over SQLite.
- **Disaster Resource Allocation** (this repository) — a database design
  exercise: normalized schema, triggers, stored procedures, transactions and
  concurrency experiments in MySQL.

[`docs/AUDIT.md`](docs/AUDIT.md) is the measured record of what ResNav actually
did before the merge: which of its README's claims held up, which did not, and
the defects found. [`docs/MAPPING.md`](docs/MAPPING.md) then reconciles the two
schemas into one, with the usage evidence behind every keep, drop and add. It is the reason this README is allowed to say what it says.
[`docs/RESNAV_ORIGINAL_README.md`](docs/RESNAV_ORIGINAL_README.md) is the old
README, kept for provenance — treat its claims as unverified unless
`docs/AUDIT.md` confirms them.

## Roadmap

| Phase | What | Status |
|---|---|---|
| 0 | Audit ResNav: build it from scratch, measure every claim | **done** — [`docs/AUDIT.md`](docs/AUDIT.md) |
| 1 | Restructure the repo, import ResNav, unify configuration | **done** |
| 2 | Unified data model: old→new mapping, ER diagram, 3NF/BCNF | **done** — [`MAPPING.md`](docs/MAPPING.md), [`DESIGN.md`](docs/DESIGN.md), [`NORMALIZATION.md`](docs/NORMALIZATION.md) |
| 3 | The MySQL layer: DDL, triggers, procedures, views, SQL tests | **done** — `make schema`, 14 SQL tests |
| 4 | Port the backend from SQLite to MySQL; dispatch calls the procedure | **done** |
| 5 | One deterministic seed, plus a tiny hand-checkable set | **done** — `make reset` |
| 6 | Concurrency proof: oversell, isolation levels, deadlock | **done** — [`CONCURRENCY.md`](docs/CONCURRENCY.md) |
| 7 | Surface alerts, audit log and "why this centre" in the UI | **done** — [screenshots](docs/screenshots/) |
| 8 | Run anywhere: Docker and a no-Docker local path | not started |
| 9 | Measure, rewrite this README, interview notes | not started |

## Layout

```
backend/     Flask app factory, 6 API blueprints, 8 AI modules, services,
             the data layer (SQLite today, MySQL from Phase 4), 51 tests
frontend/    React 18 + Vite SPA, 15 routes, design-token CSS
db/          the MySQL layer — schema, triggers, procedures, views, seed,
             SQL tests. Empty until Phase 3; see db/README.md for the contract
docs/        design, audit, and the write-ups each phase produces
tools/       capabilities.sql (server feature probe), check_mermaid.py
```

## The data

`make reset` builds the schema and loads a deterministic seed — same bytes
every time, from a fixed generator seed, so a number reproduced from this
README is the same number:

| | |
|---|---|
| relief centres | 30, across 21 cities and 16 states |
| resources | 45 |
| disaster zones | 12 |
| stock rows | 596, of which 82 open at zero |
| total units held | 108,150 |
| stock movement history | 2,345 rows |
| open requests | 600 |

Regenerate with `python3 db/seed/generate.py`; `--check` verifies the
committed files are current. The totals above come from
[`db/seed/MANIFEST.json`](db/seed/MANIFEST.json), which the generator writes
from the same data it emits, so they cannot drift.

The tests use a separate, deliberately tiny set — three centres, two
resources, one zone — documented in
[`db/tests/EXPECTED.md`](db/tests/EXPECTED.md), where every expected number is
worked out on paper.

## Getting started

**Prerequisites:** Python 3.11+, Node 20+, MySQL 8.0.16+. 8.0.16 is the floor
because that is the version where `CHECK` constraints began to be *enforced*
rather than parsed and ignored. Development is on MySQL 9.5.0.

Create the database and an account for it, as a MySQL administrator:

```sql
CREATE USER IF NOT EXISTS 'resnav_app'@'localhost' IDENTIFIED BY '<password>';
CREATE DATABASE IF NOT EXISTS resnav
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON resnav.* TO 'resnav_app'@'localhost';
GRANT SELECT ON performance_schema.* TO 'resnav_app'@'localhost';
```

Rights on the project's own schema are all that is needed — `./run.sh check`
creates its scratch objects inside `resnav` rather than in a database of its
own, precisely so the account never needs a global `CREATE`.

**If your server has binary logging enabled**, you will also need:

```sql
SET PERSIST log_bin_trust_function_creators = 1;
```

Without it MySQL refuses to let a non-`SUPER` account create triggers or
stored functions (error 1419), because a non-deterministic routine written to
the binary log can compute a different result on a replica and silently drift.
This project's functions are declared `DETERMINISTIC NO SQL`, and a
single-node development server has no replica to drift from. `./run.sh check`
tells you whether you need this. `SET PERSIST` survives a restart.

```bash
./run.sh install                      # backend venv + frontend dependencies
cp .env.example .env && chmod 600 .env   # then edit it
./run.sh check                        # verify MySQL access and features
```

One `.env` at the repo root configures the database, the API and the frontend
together. `run.sh` parses it and exports every key before starting anything,
because the Flask settings layer reads the process environment directly.

Your MySQL password is never put on a command line. `run.sh` writes a
`chmod 600` temporary defaults file and passes `--defaults-extra-file`, so the
password stays out of `ps` output and shell history.

### Running it

```bash
./run.sh api     # Flask on http://127.0.0.1:5001
./run.sh web     # Vite on http://localhost:5173, proxying /api
```

`make` delegates to `run.sh` for every target, so the two cannot drift apart.

| Target | Does | Works today |
|---|---|---|
| `install` | backend venv + `npm install` | yes |
| `check` | MySQL access and SQL feature probe | yes |
| `docs` | grammar-check the Mermaid diagrams | yes |
| `test` | backend suite + SQL suite | yes — 53 + 14 tests |
| `concurrency` | two-session race, isolation and deadlock experiments | yes — 6 experiments |
| `lint` | `ruff` + `eslint` | yes |
| `build` | production frontend build | yes |
| `api` / `web` | development servers | yes |
| `schema` | create tables, triggers, procedures, views | yes |
| `seed` / `reset` | load sample data / rebuild everything | yes |
| `demo` | end-to-end worked demo | **no** — Phase 8 |

Targets that are not built yet fail with the phase they arrive in rather than
pretending to succeed.

## Screenshots

Captured from the running app against the deterministic seed, so every number
is reproducible with `make reset`. See
[`docs/screenshots/`](docs/screenshots/README.md).

| | |
|---|---|
| [Standing low-stock alerts](docs/screenshots/stock-alerts.jpg) | Raised by a trigger when stock crossed its threshold, resolved automatically when it recovers |
| [Audit trail](docs/screenshots/audit-log.jpg) | Append-only. The `stock_update` rows are written by a trigger, so no caller can skip them |
| [Allocation plan](docs/screenshots/allocation-plan.jpg) | Distances 3.8 → 593.3 → 663.8 → 788.0 → 833.8 km: nearest-first, ordered by the database |

## Limitations and known defects

Kept here deliberately. See [`docs/AUDIT.md`](docs/AUDIT.md) for the evidence.

- **No allocations are pre-seeded.** The 600 requests all start `pending`,
  because allocating them is what the demo, the tests and the concurrency
  scripts *do* — a seed that had already run it would hide whether it works.
- **Running the tests overwrites the development data.** The suite reloads
  the seed before every test, so the tests are isolated from each other, but
  by default they share the development database. `./run.sh test` reloads the
  seed afterwards, and the seed is deterministic, so nothing is lost. Set
  `DRA_MYSQL_TEST_DB` to use a separate database (which needs its own
  `GRANT ALL`).
- **Semantic search is weak** on the very example the old README led with —
  the semantic term contributes ~0.07 while proximity contributes 1.00. The
  ranking is real and explainable; the signal is not yet good.
- **`docker-compose.yml` is the old SQLite stack and has never been run.**
  Docker is not installed on the development machine. Rewritten in Phase 8.
- **`npm audit` reports high and moderate vulnerabilities**, not yet triaged.
- **No authentication.** Every caller can allocate.
- **No deployment.** Nothing has been deployed anywhere.

## Licence

MIT — see [LICENSE](LICENSE).

---
Part of my portfolio: [github.com/Kunal0626](https://github.com/Kunal0626)
