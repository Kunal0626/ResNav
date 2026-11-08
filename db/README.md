# `db/` — the MySQL layer

This is the source of truth for stock and allocation. Everything here is
hand-written SQL: no ORM, no migration framework generating it for us.

Applied by `make schema` in the order below; `make reset` adds the seed.

## Layout and load order

Files are applied in lexical order within each directory, and the directories
are applied in the order below. The numeric prefixes exist because order
matters: a view cannot be created before its tables, and a trigger that calls
a function needs the function first.

| Order | Directory | Holds | |
|---|---|---|---|
| 1 | `schema/` | `CREATE TABLE`, keys, `CHECK` constraints, indexes | ✔ |
| 2 | `procedures/` | stored functions first (`fn_haversine_km`), then procedures | ✔ |
| 3 | `triggers/` | the ten invariant guards | ✔ |
| 4 | `views/` | the nine analytical views | ✔ |
| 5 | `seed/` | deterministic data from `generate.py` | ✔ |
| — | `tests/sql/` | 14 `.sql` + `.expected` pairs, run by `runner.py` | ✔ |
| — | `tests/concurrency/` | 6 two-session experiments, `make concurrency` | ✔ |

`make reset` runs 1 → 5 against a freshly dropped database. `make schema` runs
1 → 4 only, leaving the data alone.

## Rules this directory follows

- **MySQL 8.0.16+ syntax.** 8.0.16 is the version where `CHECK` constraints
  began to be *enforced* rather than parsed and ignored, so it is the floor.
  Development is on 9.5.0; `tools/capabilities.sql` is what proves a given
  server supports everything used here.
- **Every object is idempotent to apply.** `DROP ... IF EXISTS` before
  `CREATE`, so re-running a file is never an error.
- **Negative tests are first-class.** A constraint or trigger that is supposed
  to reject something has a test that asserts the *exact* error number and
  message. A test that expects a failure and gets silence is a failing test.
- **Money-like values are `DECIMAL`, never `FLOAT`.** Quantities are
  `DECIMAL(12,3)`. The imported SQLite schema used `REAL`, which makes exact
  comparison unreliable and would make the hand-checkable seed uncheckable.
- **Timestamps are `DATETIME(6)`.** Microsecond precision, because the
  concurrency scripts in Phase 6 need to order events that happen inside the
  same second.
