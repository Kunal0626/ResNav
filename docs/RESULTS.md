# Measurements

Every number here was produced by `make bench`, which is
[`bench/measure.py`](../bench/measure.py) in this repository. Re-run it and
you get your own figures on your own machine. Nothing in this file was
estimated, rounded up, or carried over from a previous run.

Captured 2026-11-08.

| | |
|---|---|
| machine | Apple M3, macOS (Darwin 25.6.0, arm64) |
| MySQL | 9.5.0, InnoDB, REPEATABLE READ |
| Python | 3.14.6, PyMySQL 2.2.8 |
| data | 30 centres, 45 resources, 12 zones, 596 stock rows, 600 requests, 2,345 history rows |

The data is the deterministic seed (`make reset`), so these are reproducible
rather than merely repeatable.

---

## Allocation

`CALL sp_allocate_request` — 25 units of Sleeping Mats for the Assam Flood
Zone, on a freshly created request each time so no two runs contend for the
same row or time a no-op.

| | |
|---|---|
| samples | 60 |
| p50 | **0.542 ms** |
| p95 | 0.938 ms |
| p99 | 1.018 ms |
| max | 2.898 ms |
| throughput | **1,845 allocations/sec** at the median, single session |
| legs | median 1 per allocation |

That is the complete operation: lock the request, lock every candidate stock
row in primary-key order, rank by haversine distance, insert the allocation,
and let the triggers move the stock, advance the request status, write the
history row, write the audit row and raise any low-stock alert.

**Throughput is single-session.** It is `1000 / p50`, not a concurrency
measurement. `sp_allocate_request` deliberately serialises allocations of the
same resource (it locks every candidate row up front — see
[CONCURRENCY.md](CONCURRENCY.md)), so concurrent throughput for one resource
will be lower than this and concurrent throughput across different resources
higher. **Neither was measured.**

## Where the index earns its place

`StockLevels` has `PRIMARY KEY (provider_id, resource_id)` and a secondary
index the other way round, `(resource_id, provider_id)`. The argument for the
second one is the leftmost-prefix rule: the primary key answers "what does
centre 4 hold" and cannot answer "which centres hold resource 12" — the
allocator's question on every run.

The measurement does not support that argument at this data size, and saying
so is the point of measuring.

### On the real table, 596 rows

| | without the index | with the index |
|---|---|---|
| access | `Single-row index lookup on sl using PRIMARY` | `Index lookup on sl using ix_stocklevels_resource_provider` |
| type | `eq_ref` | `ref` |
| rows estimated | 1 | 17 |
| p50 | 0.184 ms | 0.195 ms |

**0.94× — no improvement, slightly slower, within noise.** With the index
unavailable the optimiser simply reverses the join: it drives from
`Providers`, all 30 of them, and does one primary-key lookup into
`StockLevels` per provider. At this size that is a perfectly good plan.

Two things follow, and both are more interesting than a speedup would have
been.

**The index cannot be dropped at all.** The comparison above uses
`IGNORE INDEX` because `ALTER TABLE ... DROP INDEX` is refused:

```
ERROR 1553 (HY000): Cannot drop index 'ix_stocklevels_resource_provider':
needed in a foreign key constraint
```

InnoDB requires an index whose leftmost column is the referencing column of a
foreign key, and `fk_stocklevels_resource` is on `resource_id` — which this
index leads with. So it is not an optimisation the schema could choose to
omit. It is load-bearing twice over, and the query planner was always going
to have it available.

**It is insurance, not a current win.** The right claim is that the index
costs nothing to keep, is mandatory for the foreign key, and becomes
necessary as the table grows — not that it makes the application faster
today, which it does not.

### On a synthetic table, 200,000 rows

Same query shape, a scratch table with no foreign keys so the index really
can be dropped. Synthetic data, and labelled as such.

| | without the index | with the index |
|---|---|---|
| access | `Filter: (resource_id = 123 and quantity > 0)` | `Filter: (quantity > 0)` |
| type | `ALL` — full table scan | `ref` |
| rows estimated | 200,196 | 400 |
| p50 | 19.599 ms | **0.901 ms** |
| p95 | 21.785 ms | 1.017 ms |

**21.7× faster.** This is where the leftmost-prefix rule stops being a
technicality: the optimiser can no longer rescue the query by reversing the
join, because the other side is no longer 30 rows.

## The haversine function

`fn_haversine_km`, one call, 200 samples: **p50 0.058 ms**, p95 0.070 ms.

Worth knowing because the allocator calls it once per candidate centre in its
`ORDER BY`. At 30 centres that is under 2 ms of function evaluation, which is
why the allocation p50 above is dominated by the locking and the inserts
rather than the distance maths. Precomputing a distance matrix would be
optimising the wrong thing — which is why `DESIGN.md §6.2` says to measure
before building one.

## The views

Each a full read, 60 samples.

| view | rows | p50 | p95 |
|---|---|---|---|
| `v_provider_reliability` | 30 | 0.332 ms | 0.358 ms |
| `v_center_stock_summary` | 596 | 3.129 ms | 3.788 ms |
| `v_zone_shortage_analysis` | 12 | 3.295 ms | 4.363 ms |
| `v_request_fulfilment` | 660 | 10.986 ms | 16.449 ms |

`v_request_fulfilment` is the slow one, and predictably: it `LEFT JOIN`s
`Allocations` and aggregates per request across 660 rows. `v_zone_shortage_analysis`
is built on top of it, which is why 12 output rows still cost 3 ms.

Both are well inside a web request's budget at this size and neither has been
optimised, because nothing has yet shown that either needs to be.

## Tests

| suite | count | command |
|---|---|---|
| Python, against MySQL | 55 | `make test` |
| SQL, with 6 negative cases | 14 | `make test` |
| concurrency experiments | 6 | `make concurrency` |

The SQL suite reloads its fixture before every test, so it is order
independent — verified by three consecutive runs. The Python suite was not,
until Phase 4 fixed it; see [AUDIT.md](AUDIT.md).

## Not measured

Stated so that nothing here is read as more than it is.

- **Concurrent throughput.** Every latency above is a single session. Phase 6
  proves correctness under contention; it does not measure capacity.
- **Anything above 200,000 rows**, and the 200,000-row table is synthetic:
  uniform data, no realistic skew, no concurrent writers.
- **The AI endpoints.** Forecasting, risk, anomaly detection and simulation
  fit scikit-learn models per request and were not timed.
- **Frontend performance.** No Lighthouse run, no bundle budget, no
  first-paint measurement. The Vite build reports ~1.3 s and the largest
  chunk is 182 kB (64 kB gzipped), which is build output, not a user-facing
  metric.
- **Anything on another machine.** One laptop, one run each.
