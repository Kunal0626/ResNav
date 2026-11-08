# Interview notes

Two parts: the decisions and what they cost, then the fifteen hardest
questions an interviewer could reasonably ask about this project.

Everything here is answerable from the repository. Where a claim rests on a
measurement, the measurement is in [RESULTS.md](RESULTS.md); where it rests
on an experiment, the experiment is in `db/tests/concurrency/`.

---

## Part 1 — decisions, alternatives, and what each cost

| Decision | The alternative | Why this one, and the cost |
|---|---|---|
| Allocation lives in a **stored procedure** | Keep it in Python, as the SQLite version had it | Python could not hold a lock across its read-then-decide. Cost: the logic is harder to unit-test and lives away from the rest of the code. |
| **Lock every candidate up front, in primary-key order** | Lock each row as it is drawn from, in distance order | Distance order differs per zone, so two zones would lock the same centres in opposite orders — a deadlock. Cost: allocations of the same resource serialise. |
| Keep **ResNav's table names** | Rename to the design document's | Renaming touched 421 lines of `queries.py`, every AI module and the frontend, to behave identically. Cost: mixed-case tables next to snake_case views. |
| `DECIMAL(12,3)` for quantities | `FLOAT`/`REAL`, as inherited | Stock arithmetic that drifts is a correctness bug, and the hand-checked seed needs exact equality. Cost: a conversion at the driver boundary, because `Decimal` will not mix with `float` in the AI modules. |
| **Triggers** for invariants | Enforce in the service layer | A guarantee that only holds when you go through the app is not a guarantee. Cost: invisible control flow; a `DELETE` that mysteriously fails is harder to debug. |
| **Cancel releases, never deletes** | `DELETE` the allocation rows | "We promised this and took it back" is auditable information. Cost: every query about current commitments must filter `status = 'active'`, so the views do it centrally. |
| `ON DELETE RESTRICT` by default | `CASCADE`, as inherited | Deleting a resource should not erase every allocation ever made of it. Cost: you cannot delete a request with history at all — which is why `sp_cancel_request` exists. |
| **Reject the reserve-then-ship model** | Build `shipments`, as the design doc argued | It needed an API and a UI change against a brief that froze both. Cost: no distinction between "promised" and "physically gone". |
| **PyMySQL** | mysql-connector-python | Pure Python, no build step on Apple Silicon, `DictCursor` maps onto the old `sqlite3.Row` usage. Verified `CALL`+OUT, `DECIMAL` and `SIGNAL` before committing. |
| **Monochrome interface** | A colour palette | Almost everything on screen is a *state*, and a coloured chrome competes with the only colour that means anything. Cost: severity needs a second signal — fill and shape — and a lint rule to keep it that way. |
| `IGNORE INDEX` to measure the index | Drop it and measure | It **cannot** be dropped: the foreign key requires it (error 1553). Cost: measures the read benefit only, not the write cost. |

---

## Part 2 — the fifteen hardest questions

### 1. Your SQLite version had no oversell bug. Porting it to MySQL would have created one. Why?

SQLite's `BEGIN IMMEDIATE` takes a **database-wide** write lock, so there was
only ever one writer. The read-then-decide-then-write allocator was safe not
because it was correct but because nothing could run beside it.

InnoDB has row-level locking and many concurrent writers. The gap between
`recommend()` reading balances and `execute()` acting on them becomes a real
race: two sessions read the same stock, both build a plan against it, both
commit. Experiment 1 in [CONCURRENCY.md](CONCURRENCY.md) shows twenty units
promised where ten exist.

The conditional `UPDATE ... WHERE quantity >= ?` is not enough on its own. It
makes the *write* atomic, so stock never goes negative — but the decision was
already made against a stale number, so the second session gets an error
instead of a correct partial allocation.

### 2. You have a `CHECK (quantity >= 0)` and a trigger raising `SIGNAL '45000'` for the same condition. Isn't that redundant?

No, and experiment 2 shows why. The `CHECK` protects the **data**; the
trigger produces a usable **error**. A constraint violation says
`Check constraint 'ck_stocklevels_quantity' is violated`; the trigger says
`stock_negative: provider 1 resource 6 would fall to -1.000`.

If I had to drop one, I would drop the trigger: the constraint is the
backstop that holds even if a trigger is accidentally dropped during a
migration, which is the failure I actually fear.

### 3. Walk me through a deadlock you caused on purpose.

Two sessions, two stock rows, both needing both locks. Session A takes
centre 1 then centre 2; session B takes 2 then 1. Each ends up holding what
the other needs; InnoDB detects the cycle, picks a victim and rolls it back
with error 1213. Experiment 5.

The same test with both sessions taking the locks in the *same* order does
not deadlock at all — one simply waits. No retry loop, no backoff: the cycle
cannot form. That is why `sp_allocate_request` always locks by
`(provider_id, resource_id)` and never in the distance order it allocates in.

### 4. Would SERIALIZABLE have prevented the oversell?

No, and experiment 4 measures it. Under READ COMMITTED a repeated read
returns the new value (10 → 999); under REPEATABLE READ and SERIALIZABLE the
snapshot holds and it stays 10.

None of them helps. A snapshot that cannot change is still **stale** the
instant the other transaction commits. Isolation level governs what a
transaction *sees*; only a lock governs what another transaction may *do* in
between. Raising the isolation level is not a substitute for
`SELECT ... FOR UPDATE`.

### 5. Your concurrency test found a bug 67 passing tests had missed. What was it?

`sp_allocate_request` locked every candidate row in pass 1, then planned from
a **plain** `SELECT` in pass 2. In REPEATABLE READ a plain `SELECT` reads the
transaction's snapshot while a locking read reads the latest committed row.
So a session that had just waited for another to commit acquired its locks
correctly and then planned against the quantities as they were *before* that
commit — allocating stock that had already gone, and getting `stock_negative`
from the guard.

The lock was right and the read was stale. Fixed by making pass 2
`FOR UPDATE` too, which takes no new locks because pass 1 already holds every
row it can return.

Fifty-three Python tests and fourteen SQL tests passed with that bug present,
because every one of them is single-session. That is the argument for the
concurrency scripts in one sentence.

### 6. Is your schema in 3NF? In BCNF?

BCNF everywhere except two tables, both deliberate and documented in
[NORMALIZATION.md](NORMALIZATION.md).

`Providers` keeps `pincode → city, state`, a transitive dependency. The
lookup table would be joined by nothing else, and `pincode` is nullable — so
the decomposition would *lose* city and state for exactly the rows most
likely to be incomplete.

`EmergencyContact` keeps `number → name`. It is in 3NF because `name` is
prime, and not in BCNF because `number` is not a superkey.

### 7. Then justify leaving `EmergencyContact` in 3NF.

The BCNF decomposition — `ContactNumber(number, name)` and
`ContactCoverage(number, region)` — is lossless but **not
dependency-preserving**. The dependency `(name, region) → number` spans both
tables afterwards, so "one number per service per region" can no longer be
enforced by a key and would need a trigger.

Trading a declarative constraint for a procedural one, to protect six rows of
hand-maintained reference data against an anomaly nobody can reach through
the UI, is a bad deal. Knowing *which* of lossless-join and dependency
preservation you gave up is the actual question.

### 8. Why does an index on `(item_id, center_id)` differ from one on `(center_id, item_id)`?

A composite index is sorted by its first column, then its second — a phone
book by surname then first name. It can satisfy a lookup fixing a **leftmost
prefix** of its columns and no other.

`PRIMARY KEY (provider_id, resource_id)` answers "what does centre 4 hold".
It cannot answer "which centres hold resource 12" without a scan, any more
than a phone book can find everyone named Kunal.

### 9. So how much did that second index speed things up?

**It did not.** On the real table, 596 rows: 0.184 ms without, 0.195 ms with
— no improvement, within noise. With the index unavailable the optimiser
simply reverses the join, driving from the 30 `Providers` rows and doing a
primary-key lookup each.

Two things make that worth saying. First, the index **cannot be dropped** —
`fk_stocklevels_resource` requires it, MySQL error 1553 — so it was never
optional. Second, on a 200,000-row table of the same shape it is **21.7×**
faster: full scan of 200,196 rows versus an indexed lookup of 400.

The honest claim is that it is free, mandatory, and insurance against growth
— not that it makes the application faster today.

### 10. What are the ACID properties, with an example from this project?

- **Atomicity** — `sp_cancel_request` releases every allocation, returns the
  stock to each centre and sets the request to rejected. A failure partway
  leaves none of it applied; the `EXIT HANDLER` rolls back and `RESIGNAL`s.
- **Consistency** — allocating 11 units from a centre holding 10 is refused
  by `trg_allocations_bi_validate`, and `CHECK (quantity >= 0)` underneath it.
  No committed state ever has negative stock.
- **Isolation** — experiment 3: two sessions allocate the last ten units
  simultaneously; exactly ten are handed out and the second correctly
  receives nothing.
- **Durability** — committed allocations survive a restart. The weakest of
  the four here: I have not tested a crash mid-transaction, and I would not
  claim I had.

### 11. When would you avoid triggers?

When the logic needs a transaction of its own (a trigger cannot `COMMIT` or
`ROLLBACK`), when it would need to modify the table that fired it (MySQL
forbids it — which is why the low-stock alert writes to `StockAlerts` rather
than flagging the stock row), and when a bulk load would pay the per-row cost
unnecessarily.

More generally: triggers are invisible. A `DELETE` that mysteriously fails is
harder to debug than a function you can read, and triggers firing triggers is
worse. I used them only for invariants that must hold against *every* client,
and put every decision in a procedure.

### 12. `SELECT ... FOR UPDATE` — what does it lock, and in which isolation levels?

It takes exclusive row locks on the rows it reads, plus gap locks under
REPEATABLE READ to stop phantoms appearing in the scanned range. Under READ
COMMITTED there are no gap locks, so only the matched rows are locked.

Critically, it locks **rows the scan touches**, not just rows that match — so
a query that cannot use an index locks far more than it needs. That is a
second, quieter reason the `(resource_id, provider_id)` index matters.

### 13. MySQL has no partial indexes. How did you enforce "at most one open alert per centre and resource"?

PostgreSQL would write `UNIQUE (...) WHERE status = 'open'`. MySQL has no
`WHERE` on an index, but it has a rule that can be turned into one: **a
multi-column `UNIQUE` index ignores rows where any indexed column is `NULL`.**

So two generated columns go `NULL` the moment an alert resolves. Open rows
are held unique; resolved rows are free to repeat.

The same rule is a hazard elsewhere: `UNIQUE (parent_region_id, name)` would
silently permit two identically-named roots, because `NULL`s do not collide.

### 14. Your low-stock trigger uses an upsert instead of checking first. Why?

Check-then-insert is a race. Two sessions both find no open alert, both
insert, and the second hits the unique index — raising an error **inside a
trigger**, which fails the `UPDATE` to `StockLevels` that fired it, which
rolls back a perfectly valid allocation. A monitoring feature able to break
the thing it monitors.

`INSERT ... ON DUPLICATE KEY UPDATE id = id` is one atomic statement with no
window to lose and no error to handle. The index guarantees the invariant and
the upsert makes hitting it harmless.

### 15. What is the weakest part of this project?

The semantic search. The ranking is real and explainable — the UI shows
`[Sem: 0.07, Stock: 0.93, Dist: 1.00, Urg: 0.35]` — but on the example the
old README led with, intent classifies as `unknown` at 18.6% confidence and
the semantic term contributes almost nothing. It is TF-IDF over short
provider descriptions, which is not enough text for the method to work.

Close behind: no authentication, so every caller can allocate; no expiry or
batch tracking, so stock cannot be allocated oldest-first; and no concurrent
throughput measurement, so I can say allocation is correct under contention
but not how much of it the system sustains.

---

## If I had another week

1. Fix the test isolation properly at the *driver* level rather than by
   reloading a seed — a transaction per test, rolled back.
2. Measure concurrent throughput, which is the obvious hole in
   [RESULTS.md](RESULTS.md).
3. Batch and expiry tracking on `StockLevels`, so perishable stock can be
   allocated oldest-first. It is the largest honest gap in the data model.
4. Replace TF-IDF with a sentence-transformer behind the existing encoder
   interface and measure whether the ranking actually improves, rather than
   assuming it would.
