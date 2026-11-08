# Resume bullets

Two candidates. Every number in them is measured and traceable to something
in this repository — see the audit table at the bottom. Bullets I could not
support are listed at the end with what would be needed to earn them.

---

## Bullet 1 — the correctness story (recommended)

> Built a relief-allocation system in MySQL 8 where 10 triggers and 5 stored
> procedures enforce stock invariants; demonstrated with two-session tests
> that the prior read-then-write design oversold stock (20 units committed
> against 10 in inventory) and that ordered `SELECT … FOR UPDATE` eliminates
> it, at 0.54 ms median allocation latency.

**Why this one.** It is the only bullet on a fresher's resume that says *I
found a concurrency bug and proved I fixed it*. It names the mechanism, so an
interviewer can go three questions deep, and every number survives being
asked "how do you know?".

Shorter, if space is tight:

> Moved relief allocation from application code into a MySQL stored procedure
> with ordered row locking, eliminating an oversell demonstrated by
> two-session tests (20 units committed against 10 held); 0.54 ms median
> allocation latency, 10 triggers and 22 CHECK constraints enforcing the
> invariants.

## Bullet 2 — the engineering story

> Ported a Flask + SQLite application to MySQL 8 without breaking its
> 22-endpoint API contract: moved allocation into a stored procedure, fixed a
> test-isolation defect that had 53 tests passing against the developer's
> live database, and added 14 SQL tests including 6 negative cases asserting
> exact error codes.

**Why this one.** It reads as maintenance work and is actually the harder
skill: changing the engine underneath a running application while keeping its
contract. The isolation defect is the strongest detail — it says the
candidate reads test output sceptically.

Shorter:

> Ported a Flask application from SQLite to MySQL 8 with no change to its
> 22-endpoint API contract; added 14 SQL tests with 6 negative cases
> asserting exact error numbers, and fixed a defect that let 53 tests pass
> against the wrong database.

---

## Where each number comes from

| Claim | Evidence |
|---|---|
| 10 triggers, 5 stored routines, 22 `CHECK`s, 17 FKs, 9 views, 17 tables | `information_schema`, reported by `make schema` |
| 20 units committed against 10 held | `db/tests/concurrency/c01_oversell_unguarded.py`, quoted in `docs/CONCURRENCY.md` |
| ordered `SELECT … FOR UPDATE` eliminates it | `c03_real_allocator.py` and `c06_http_api.py`: exactly 10 units out, no error, HTTP 200 + 409 |
| 0.54 ms median allocation latency | `make bench`, n=60, p50 0.542 ms — `docs/RESULTS.md` |
| 22 endpoints | route table in `docs/AUDIT.md`; 26 registered, 22 exercised |
| 53 tests passing against the wrong database | `docs/AUDIT.md` "Broken test isolation", with the before/after row counts |
| 14 SQL tests, 6 negative | `db/tests/sql/`, run by `make test` |
| API contract unchanged | all 22 endpoints re-probed after the port, same shapes and field names |

## Bullets I cannot support yet

Listed so they are not written by accident.

- **needs: a concurrent throughput measurement.** "Handles N concurrent
  allocations per second" — the 1,845/sec figure in `docs/RESULTS.md` is
  *single-session*, which is a latency reciprocal, not capacity. Would need a
  load generator with a ramp.
- **needs: a before/after on the real table.** "Cut query time 21×
  with a composite index" — true only on a synthetic 200,000-row table. On
  the actual 596-row data the index makes no measurable difference, and it
  cannot even be dropped because a foreign key requires it.
- **needs: a deployment.** "Deployed to production" — nothing is deployed and
  no hosting account exists.
- **needs: a user.** Anything about adoption, operators served or relief
  delivered. This is a portfolio project with synthetic data.
- **needs: an accuracy measurement.** "AI-powered semantic search" — the
  ranking is real and explainable, but on the project's own example query
  the semantic term contributes 0.07 against proximity's 1.00. Claiming it
  works would not survive the follow-up question.
