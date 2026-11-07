# Reconciling the two schemas

Phase 2 deliverable. Two schemas have to become one: ResNav's live SQLite
schema (18 tables, 12 views, 5 triggers, 40 indexes) and the MySQL design in
[DESIGN.md](DESIGN.md), which was written for the same domain but never built.

This document decides what the merged schema is, and shows the evidence behind
each decision. The DDL that implements it is Phase 3.

## Method

Decisions here are driven by **what the code actually does**, not by what the
schemas say. Every table, view and column in ResNav's `schema.sql` was counted
against every reference in `backend/app/**/*.py`, `backend/tests/*.py` and
`frontend/src/**`. The counts below are reproducible:

```bash
grep -rhoE "\b(FROM|JOIN|INTO|UPDATE)\s+[A-Za-z_][A-Za-z0-9_]*" backend/app --include='*.py' \
  | awk '{print $2}' | sort | uniq -c | sort -rn
```

## Three findings that shaped the result

### 1. Every one of the twelve views is dead

Not one is referenced anywhere outside `schema.sql`:

| View | References in code |
|---|---|
| `ResourceType`, `ResourceStock`, `ResourceRequest`, `Allocation` | 0 |
| `ServiceProvider`, `Location` | 0 — the two apparent hits are both the same code comment |
| `v_center_stock_summary` | 0 |
| `v_high_risk_zones`, `v_fastest_depleting_resources` | 0 |
| `v_provider_efficiency`, `v_allocation_performance` | 0 |
| `v_zone_shortage_analysis` | 0 |

The schema advertises an "ANALYTICAL SQL VIEWS" section as evidence of DBMS
depth. In reality the Python layer recomputes all of it: `services/analytics.py`
and the AI modules aggregate in pandas-free Python over rows pulled from base
tables. The views are decoration.

This is the most important thing to fix, and the fix is *not* to delete them.
Six of them (the backward-compatibility shims) should go, because they map old
table names onto new ones for callers that no longer exist. The five analytical
ones should be rewritten and then **actually used** — moving aggregation out of
Python and into SQL is both better architecture and the thing that makes the
DBMS claim true.

### 2. Three tables are maintained for nobody

`RiskScores`, `ZoneSummary` and `ResourceConsumptionRate` are written by
triggers and by the seeder, and **never read by the application**. The only
references outside `schema.sql` are inside `seed.py`'s own
`INSERT OR IGNORE ... SELECT` statements.

`schema.sql` claims above `RiskScores` that "Forecast module reads from this
table directly". It does not: `ai/forecast_engine.py` runs `LinearRegression`
over `StockHistory`. The comment is wrong.

Trigger-driven materialised aggregation is a genuinely good thing to
demonstrate. It is only worth keeping if something reads the result, so these
three tables survive on condition that Phase 4 wires the dashboard to them.

### 3. Zones have no coordinates, and it visibly hurts

`Zones` stores `region` and `state` but no latitude or longitude.
`services/allocation.py` says so itself:

> Zones carry no coordinates in the schema, so proximity is approximated by
> state match rather than the previous code's distance-from-Delhi

So allocation ranks suppliers by *same-state or not* — a boolean standing in
for distance. Meanwhile `Providers` does carry `latitude`/`longitude`, and
search already computes real haversine distances with them.

Adding two columns to `Zones` makes `fn_haversine_km()` usable on the allocation
path, replaces a boolean with a real distance, and turns "why this centre"
into a statement with a number in it. This is the single highest-value change
in the merge and it costs two columns.

## Decisions

### Names: ResNav's win

The merged schema keeps `Providers`, `StockLevels`, `Requests`, `Allocations`
and friends, not DESIGN.md's `relief_centers`, `center_stock`, `requests`,
`allocations`.

Renaming would touch all 421 lines of `queries.py`, every AI module, the
seeder, the tests and parts of the frontend, to make the code read differently
while behaving identically. DESIGN.md's value is its *reasoning*, which
transfers; its names do not.

New objects added by this project use `snake_case` with a prefix: `v_` for
views, `sp_` for procedures, `fn_` for functions, `trg_` for triggers.
Mixed-case tables beside lower-case views is not pretty, but churn is worse.

> **Portability note.** The development server reports
> `lower_case_table_names = 2` (macOS: stored as written, compared
> case-insensitively). A typical Linux server uses `0`, where `Providers` and
> `providers` are *different tables*. The code already spells every table
> consistently, so this is safe — but the schema must never contain two names
> differing only in case, and `make check` reports the setting so the trap is
> visible.

### Types: fixing what SQLite let slide

| SQLite | MySQL | Why |
|---|---|---|
| `REAL` quantities | `DECIMAL(12,3)` | Binary floating point cannot represent 0.1 exactly. Stock arithmetic that drifts is a correctness bug, and Phase 5's hand-checkable seed needs exact comparison. |
| `TEXT` timestamps, `datetime('now')` | `DATETIME(6)`, `CURRENT_TIMESTAMP(6)` | Real temporal type, real ordering, and microseconds so Phase 6 can order events inside one second. |
| `INTEGER` + `CHECK (x IN (0,1))` | `TINYINT(1)` | The `CHECK` becomes unnecessary. |
| `TEXT` + `CHECK (x IN (...))` | `ENUM` | Declared in the type, cheaper to store, self-documenting. |
| `TEXT` free-length | `VARCHAR(n)` | Lengths are now stated rather than unbounded. |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `INT UNSIGNED AUTO_INCREMENT` | `BIGINT UNSIGNED` for the log tables, which grow without bound. |

### Table-by-table

| ResNav table | Fate | Change |
|---|---|---|
| `Resources` | keep | types only |
| `Providers` | keep | types only. Already has coordinates. |
| `Zones` | keep | **+ `latitude`, `longitude`** `DECIMAL(9,6)` with range `CHECK`s |
| `Requests` | keep | types; `status` becomes `ENUM`; **+ `closed_at`** with a `CHECK` tying it to a closed status |
| `Allocations` | keep | **+ `status ENUM('active','released')`, `released_at`** so `sp_cancel_request` can release rather than delete |
| `StockLevels` | keep | types; quantity `DECIMAL(12,3)` |
| `StockThresholds` | keep | types only |
| `StockHistory` | keep | types only. The forecast engine's real input. |
| `AuditLog` | keep | types; absorbs `SystemLog` |
| `RiskScores` | keep **on condition** | must be read by Phase 4, or it goes |
| `ZoneSummary` | keep **on condition** | same |
| `ResourceConsumptionRate` | keep **on condition** | same |
| `ServiceCategory`, `ServicesOffered` | keep | types only. Drive the search intent classifier. |
| `EmergencyContact` | keep | types only. Rendered on the results page. |
| `UserQuery` | keep | types only. Write-only by design: anonymised search log. |
| `SystemLog` | **drop** | 100% overlap with `AuditLog`, which already has `action_type`, `table_name`, `record_id` and `details`. One write site, folded into `AuditLog`. |
| `StockAlerts` | **new** (Phase 3) | Added while writing the triggers: "exactly one open alert" is a statement about state, which an append-only `AuditLog` cannot hold. See DESIGN.md §7.1b. |
| `AllocationHistory` | **drop** | Dead: zero references, including its own four indexes. Its columns (`qty_before`, `qty_after`, `action`, `performed_by`) duplicate `StockHistory` plus `AuditLog`. |

### Views

| View | Fate |
|---|---|
| `ResourceType`, `ServiceProvider`, `Location`, `ResourceStock`, `ResourceRequest`, `Allocation` | **drop** — compatibility shims for callers that no longer exist |
| `v_center_stock_summary` | keep, and wire up — it is exactly what `/api/stock` returns |
| `v_high_risk_zones`, `v_fastest_depleting_resources`, `v_provider_efficiency`, `v_allocation_performance`, `v_zone_shortage_analysis` | keep, rewrite for MySQL, **and make the application read them** |
| `v_provider_reliability` | **new** — lifts the `LEFT JOIN (SELECT ... GROUP BY provider_id)` subquery that `providers_holding_resource` inlines today |
| `v_request_fulfilment` | **new** — lifts the correlated `SUM(quantity_allocated)` subquery that `get_request` inlines today |

Those last two matter: both are derived values the code recomputes inline on
every call. Naming them makes the intent legible and gives Phase 6 something
to run `EXPLAIN` against.

## What DESIGN.md contributes, and what of it is rejected

### Adopted

| From DESIGN.md | Applied to the merged schema |
|---|---|
| `SIGNAL SQLSTATE '45000'` guards | replaces SQLite's `RAISE(ABORT, …)`; every trigger gets a named, testable error |
| Generated column instead of a redundant flag | the `is_perishable`/`shelf_life` argument; the merged `StockLevels` gets no redundant flags |
| `NULL`-in-a-unique-index as a partial index | a `stock_alerts`-style "at most one open alert" constraint, if alerts become a table |
| Atomic upsert over check-then-insert | the low-stock trigger uses `INSERT … ON DUPLICATE KEY UPDATE`, which cannot race |
| One global lock order | `sp_allocate_request` locks `StockLevels` by `(provider_id, resource_id)`, always |
| Choose unlocked, then re-read `FOR UPDATE` and re-validate | the two-step allocation that makes the Phase 6 oversell demonstration honest |
| `DECIMAL` not `FLOAT`; `DATETIME(6)` | types table above |
| `ON DELETE RESTRICT` by default | see below |

### Rejected

**`reserved` / `available` and the reserve-then-ship model** (DESIGN.md §6.1).
DESIGN.md argued that allocation should *reserve* stock and only a shipment
should remove it. That is the better warehouse model, and I am not building it.

It requires a `shipments` table, a dispatch step in the API and a dispatch
control in the UI — and this merge's brief is explicit that the API contract
stays stable and the frontend barely changes. Inventing a shipping feature to
satisfy a design document is scope creep dressed as rigour. ResNav's model
(allocation deducts stock immediately) stays; `sp_cancel_request` adds stock
back. Recorded under Limitations rather than quietly dropped.

**`regions` as a self-referencing hierarchy.** ResNav has flat
`Zones.region` + `Zones.state` text. A proper hierarchy is the honest model and
would let a recursive CTE roll reports up a real tree. But nothing in the app
navigates a hierarchy today, and normalising it means a migration plus changes
to search, seeding and three AI modules. The recursive-CTE requirement is met
instead by a genuine use: walking the `state → city → provider` grouping.
Flagged as future work.

**`item_categories`, `shipments`, `affected_areas` as separate entities.**
`Resources.category` is already a column, there is no shipping, and
ResNav's `Zones` fills the role of `affected_areas`. Adding these would be
building DESIGN.md's project rather than merging it.

### Foreign key policy

ResNav uses `ON DELETE CASCADE` almost everywhere, which means deleting a
`Resource` silently erases every allocation ever made of it. The merged schema
follows DESIGN.md instead: **`RESTRICT` by default, `CASCADE` only where the
child has no independent existence.**

| Child → Parent | ResNav | Merged | Why |
|---|---|---|---|
| `Allocations` → `Requests` | `CASCADE` | `RESTRICT` | An allocation is a record of stock having moved. It must outlive tidying up. |
| `Allocations` → `Providers`, `Resources` | `CASCADE` | `RESTRICT` | same |
| `StockLevels` → `Providers`, `Resources` | `CASCADE` | `RESTRICT` | Deleting a resource should fail while stock of it exists, not empty the warehouse. |
| `Requests` → `Zones`, `Resources` | `CASCADE` | `RESTRICT` | |
| `StockHistory`, `AuditLog` | `CASCADE` / none | **no FK** | History must survive the deletion of what it describes. |
| `ServicesOffered` → `Providers` | `CASCADE` | `CASCADE` | A junction row has no meaning without its provider. |

The interaction worth knowing: because `Allocations` now `RESTRICT`s, deleting
a `Request` that has allocations **fails** rather than erasing history. That is
the intent, and it is why `sp_cancel_request` exists — cancelling is a state
change, not a `DELETE`.

## What must not change

Phase 4 keeps the HTTP contract stable, so the merged schema must still be able
to serve, with the same field names:

- `/api/stock` → `stock[]` with `center_name`, `resource_name`, `unit`,
  `quantity`, `low_stock_threshold`, `is_low`
- `/api/requests` → `requests[]` with `zone`, `resource`,
  `quantity_requested`, `quantity_allocated`, `priority_score`, `status`
- `/api/allocations` → `allocations[]` with `provider_name`, `resource_name`,
  `quantity`, `allocated_at`, `zone`, `request_status`
- the recommendation payload: `coverage`, `reliability`, `score`, `reasoning`,
  `allocate_qty`, `confidence_score`, `allocation_type`
- the uniform error envelope `{"error": {"code", "message", "details"}}`

`reliability` has no column behind it and never did — it is computed from
`Allocations` joined to `Requests`. In the merged schema that computation moves
into `v_provider_reliability`, and the API field keeps its name and meaning.

## Open questions

1. **The three conditional tables.** `RiskScores`, `ZoneSummary` and
   `ResourceConsumptionRate` are kept only if Phase 4 makes the dashboard read
   them instead of recomputing in Python. If you would rather not touch the AI
   modules, the honest alternative is to drop all three and stop claiming
   trigger-driven materialisation. Which?
2. **`Zones` coordinates.** Adding them means the seed needs plausible
   lat/long for all five zones. Real coordinates for real districts, or
   obviously synthetic ones? (Recommendation: real coordinates, fictional camp
   names — see DESIGN.md §10.)
3. **`severity` and `urgency` ranges.** The API validates both to `0.1–3.0`,
   while `Requests.severity` only has `CHECK (severity > 0)` and DESIGN.md
   assumed an integer `1–5`. The merged `CHECK` should match the API:
   `BETWEEN 0.1 AND 3.0`. Confirm, because it changes every seeded row.
