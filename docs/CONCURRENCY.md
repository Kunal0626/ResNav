# Concurrency

Phase 6 deliverable. Everything below was produced by
`db/tests/concurrency/`, run with `make concurrency` on 2026-11-07. The
output blocks are copied from that run. **Nothing here is claimed that a
script did not print**, and where a result is timing-dependent it says so.

Machine: Apple Silicon Mac (arm64), macOS 26.6.2. MySQL 9.5.0, InnoDB,
default isolation REPEATABLE READ, `innodb_lock_wait_timeout` 50,
`innodb_deadlock_detect` ON.

Every experiment opens real, separate MySQL connections and drives them from
threads. A `threading.Barrier` releases both sessions at the same instant, so
the interleaving is forced rather than hoped for. A short sleep between a
read and the write that depends on it does not *create* any race — it makes
a race that already exists reproducible instead of appearing once a week in
production.

All six run against the tiny fixture in `db/tests/fixture.sql`: three relief
centres holding **10, 40 and 100** blankets.

---

## Why this project needed to look at all

The code this was merged from ran on SQLite, where `BEGIN IMMEDIATE` takes a
**database-wide** write lock. There was only ever one writer, so a
read-then-decide-then-write allocator was safe — not because it was correct,
but because nothing could run beside it.

InnoDB has row-level locking and many concurrent writers. Porting that code
across unchanged would have carried the same logic into an environment whose
one protective assumption no longer holds. Experiments 1 to 3 are that
argument, measured.

---

## 1. The bug, with nothing in the way

A scratch table, no `CHECK`, no trigger, no lock. Two sessions each read the
balance, each conclude 10 units are free, each write back what they computed.

```
  session A: read 10, took 10, wrote 0
  session B: read 10, took 10, wrote 0

  stock afterwards: 0
  units handed out: 10

  >> OVERSOLD. Both sessions believed they had 10 units and both took 10,
     but the stock only fell by 10. 20 units were promised and 10 exist.
```

This is the lost update in its plainest form. Twenty units were committed to
requests; ten exist. Nothing errored, so nothing would have been noticed
until a truck arrived at an empty warehouse.

## 2. The real schema, but the application decides

Same race, now against the real tables — triggers, `CHECK` constraints and
all — with the application doing its own availability check before inserting,
which is exactly what the ported SQLite code did.

```
  stock before: [(1, 10.0), (2, 40.0), (3, 100.0)]
  session A: read 10.0, allocated 10
  session B: ERROR 1644: stock_negative: provider 1 resource 1 would fall to -10.000

  stock after: [(1, 0.0), (2, 40.0), (3, 100.0)]
```

**The data is intact.** `trg_stocklevels_bu_guard` refused the second write,
and stock never went negative. The invariant held.

But the system is not correct, only incorruptible. Session B had already been
told by `recommend()` that the dispatch was possible; what it got back was an
unhandled database error. A user clicking *Dispatch* sees a failure that
looks like a bug, and a retry may or may not work.

This distinction is the whole point of the phase: **a constraint protects the
data, not the user.**

## 3. The same race, through `sp_allocate_request`

Identical setup, ten units in the entire system, two requests wanting all
ten. The only change is that the decision happens inside the database,
behind locks taken in primary-key order, with quantities read *after* the
locks are held.

```
  stock before: [(1, 10.0), (2, 0.0), (3, 0.0)]  (total 10)
  session A: allocated 10.0, legs 1, status fulfilled
  session B: allocated 0.0, legs 0, status pending

  stock after: [(1, 0.0), (2, 0.0), (3, 0.0)]
  units handed out: 10.0
  sum of active allocations: 10.0

  >> CORRECT.
```

Ten units handed out, allocations summing to the same ten, no error. Session
B was not refused — it **waited**, and then correctly found nothing to take.
Its request stays `pending`, which is a true description of its situation.

### This experiment found a real bug

On its first run, experiment 3 **failed**: session B returned
`ERROR 1644: stock_negative`. The lock was working; the read was stale.

In REPEATABLE READ a plain `SELECT` reads the transaction's **snapshot**,
established at its first read, while a locking read reads the **latest
committed** row. `sp_allocate_request` locked every candidate row in pass 1
and then planned from a plain `SELECT` in pass 2 — so a session that had
just waited for another to commit acquired its locks correctly and then
planned against the quantities as they were *before* that commit. It decided
to allocate stock that had already gone.

The fix is one clause: pass 2 is now also `FOR UPDATE`. It takes no new locks
— pass 1 already holds every row it can return — so the canonical lock order
is untouched; it reads current rows rather than the snapshot.

**Fifty-three Python tests and fourteen SQL tests passed with that bug
present**, because every one of them is single-session. There was no second
transaction to go stale against. That is the argument for writing these
scripts, stated as plainly as it can be.

## 4. What the isolation level actually changes

Session A reads a value, waits, and reads it again inside one transaction.
Session B sets it to 999 and commits in between.

```
  isolation level     1st read  2nd read   what the writer did
  --------------------------------------------------------------------------
  READ COMMITTED          10.0     999.0   committed 999
  REPEATABLE READ         10.0      10.0   committed 999
  SERIALIZABLE            10.0      10.0   committed 999

  READ COMMITTED     second read CHANGED   -> non-repeatable read
  REPEATABLE READ    second read unchanged -> snapshot held
  SERIALIZABLE       second read unchanged -> snapshot held
```

Under READ COMMITTED each statement sees the newest committed data, so the
second read returns 999: a **non-repeatable read**. Under REPEATABLE READ —
MySQL's default, and what this project runs on — the transaction keeps the
snapshot it started with, and A still sees 10. SERIALIZABLE behaved the same
way here; this experiment does not distinguish them, because it contains no
phantom and no write conflict.

**None of these levels prevents the oversell.** A snapshot that cannot change
is still stale the instant the other transaction commits, which is exactly
the failure in §3. Isolation level governs what a transaction *sees*; only a
lock held across the read and the write governs what another transaction may
*do* in between. Raising the isolation level is not a substitute for
`SELECT ... FOR UPDATE`.

It is also the mechanism behind the §3 bug: the snapshot was doing precisely
what REPEATABLE READ promises.

## 5. A deadlock, and the ordering that prevents it

Two sessions, two rows, both needing both locks. Only the order differs.

```
  PART A -- opposite orders: session A takes 1 then 2, session B takes 2 then 1
    session A: ERROR 1213: Deadlock found when trying to get lock; try restarting transaction
    session B: B: locked 2 then 1 -- committed

  PART B -- same order: both sessions take 1 then 2
    session A: A: locked 1 then 2 -- committed
    session B: B: locked 1 then 2 -- committed
```

Opposite orders deadlock: each session holds what the other needs, InnoDB
detects the cycle, picks a victim and rolls it back with **error 1213**.
Which session is chosen varies between runs — it depends on which has done
less work — so the scripts assert that *a* deadlock occurred, not which
session lost.

The same order does not deadlock. One session simply waits and both commit.
No retry loop, no backoff, no error: the cycle cannot form, because a cycle
needs two sessions holding locks in opposite order.

This is why `sp_allocate_request` locks by `(provider_id, resource_id)`
always, and never in the distance order it allocates in. Distance is relative
to the requesting zone, so two requests from different zones would rank the
same two centres in opposite orders — part A, in production.

> One honest note about the method. Part B originally used the same barrier
> as part A and produced `ERROR 1205: Lock wait timeout exceeded`, which
> looks like a database result and is not one: with the same first row the
> second session blocks before reaching the barrier, so the *barrier*
> deadlocked, in Python. The rendezvous is only valid when the two sessions
> take different first locks. A concurrency test can be wrong in the same
> way the code it tests can be.

## 6. The same race over HTTP

Through the whole stack — Flask, the connection layer, the service, the
procedure — because a guarantee that holds only when you talk to the database
yourself is not a guarantee the application has.

```
  stock before: [(1, 10.0), (2, 0.0), (3, 0.0)]  (total 10)

  request 821: HTTP 409  conflict: No provider currently holds stock of 'Blankets'.
  request 822: HTTP 200  allocated=10.0 status=fulfilled

  stock after: [(1, 0.0), (2, 0.0), (3, 0.0)]
  units handed out: 10.0

  >> CORRECT. HTTP statuses [200, 409]. No 500, no oversell, no retry needed.
```

Exactly ten units left the system. One client was served; the other was told
in ordinary HTTP terms that nothing was available. **No 500** — the database
race never reaches the client as a server fault, which is the difference
between §2 and §3 seen from outside.

Which request wins varies between runs. That is correct: the contract is that
*one* of them is served and the total is right, not that a particular one
wins.

---

## What this adds up to

| | oversell possible? | user-visible failure? |
|---|---|---|
| No constraint, no lock (§1) | **yes, silently** | none — worst case |
| Constraints, application decides (§2) | no | unhandled error 1644 |
| `sp_allocate_request` (§3, §6) | no | none; correct partial result |

- A `CHECK` constraint and a trigger make corruption impossible. They do not
  make the application correct — §2 proves both halves of that in one run.
- The isolation level decides what you *see*; the lock decides what others
  may *do*. Only the second prevents the oversell.
- A deadlock is a property of lock *order*, not of load. Ordering removes it
  entirely, which is better than retrying.
- Single-session tests cannot find concurrency bugs. Sixty-seven of them
  passed over the §3 defect.

## Reproducing

```bash
make reset          # deterministic data
make concurrency    # all six experiments, ~30 seconds
```

Individual experiments: `./run.sh concurrency c03` runs only the third.

## Not measured

- **Throughput and latency under contention.** Phase 9 measures allocation
  latency; nothing here measures how many concurrent allocations per second
  the procedure sustains, and no such number is claimed.
- **More than two sessions.** Every experiment uses exactly two. Whether
  lock contention degrades gracefully at twenty is untested.
- **SERIALIZABLE versus REPEATABLE READ in a case that distinguishes them.**
  §4 shows them behaving identically for a non-repeatable read; it contains
  no phantom read, which is where they would differ.
- **Replication, failover, or anything on more than one server.**
