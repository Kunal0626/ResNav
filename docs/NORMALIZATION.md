# Normalization

Phase 2 deliverable, and the document to read before a viva. It starts from one
deliberately bad table and decomposes it step by step into the merged schema,
naming at each step the anomaly that step removes.

The starting table is not a straw man: it is what a relief operation's
spreadsheet actually looks like before anyone normalises it, and every column
in it survives somewhere in the final schema.

---

## 0. The starting point: one flat `relief_log`

One row per "we sent some supplies somewhere".

| zone_name | zone_state | zone_population | resource_name | resource_unit | resource_category | provider_names | provider_pincode | provider_city | provider_state | provider_phone | qty_requested | severity | urgency | priority_score | status | requested_at | qty_allocated | stock_after |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Assam Flood Zone | Assam | 2000000 | Blankets | units | shelter | Karol Bagh Night Shelter, Bandra Shelter Home | 110005, 400050 | Delhi, Mumbai | Delhi, Maharashtra | 011-…, 022-… | 40 | 2.5 | 2.5 | 1041.67 | allocated | 2026-11-07 10:00 | 10, 20 | 240, 50 |
| Assam Flood Zone | Assam | 2000000 | Water Cans | litre | water | Guwahati Flood Relief Camp | 781001 | Guwahati | Assam | 0361-… | 500 | 3.0 | 3.0 | 300.00 | pending | 2026-11-07 10:05 | | |

Already unusable, and worth being specific about why rather than just saying
"it's denormalized":

- **Insert anomaly.** A new relief centre that has not yet supplied anything
  cannot be recorded at all — there is no row to put it in without inventing a
  fake request. Same for a zone with no requests yet.
- **Update anomaly.** Assam's population appears on every row for every request
  from that zone. Correcting it means finding and updating all of them; miss
  one and the database holds two different populations for one zone.
- **Delete anomaly.** Delete the last request from a zone and you lose the
  zone's population and state along with it. Deleting *history* destroys
  *reference data*.

### The functional dependencies

Writing these down first is what makes the rest mechanical rather than
intuitive. Using surrogate ids for what the entities will become:

```
F1   request_id                  → zone_id, resource_id, qty_requested,
                                   severity, urgency, priority_score,
                                   status, requested_at
F2   zone_id                     → zone_name, zone_state, zone_population
F3   resource_id                 → resource_name, resource_unit, resource_category
F4   provider_id                 → provider_name, provider_pincode, provider_phone
F5   provider_pincode            → provider_city, provider_state
F6   (request_id, provider_id)   → qty_allocated
F7   (provider_id, resource_id)  → stock_after, low_stock_threshold
F8   zone_name                   → zone_id          (zone names are unique)
F9   resource_name               → resource_id      (resource names are unique)
```

F5 is the interesting one and is genuinely true of Indian postal codes: a
pincode determines exactly one city and state. It is the source of the 3NF
violation in §3.

---

## 1. First normal form — no repeating groups

**Rule.** Every attribute holds a single atomic value; no lists, no repeating
columns.

**Violation.** `provider_names`, `provider_pincode`, `qty_allocated` and
`stock_after` each hold a comma-separated list, because one request can be
filled from several centres. Row 1 above packs two allocations into one row.

This is not a style complaint. `WHERE provider_names = 'Bandra Shelter Home'`
silently misses row 1. Summing allocated quantities needs string splitting.
The positional correspondence between the third item of `provider_names` and
the third item of `qty_allocated` is a rule the database cannot enforce, so
one careless edit silently misattributes stock.

**Fix.** One row per allocation.

```
relief_log_1nf(
    request_id, zone_name, zone_state, zone_population,
    resource_name, resource_unit, resource_category,
    provider_id, provider_name, provider_pincode, provider_city,
    provider_state, provider_phone,
    qty_requested, severity, urgency, priority_score, status, requested_at,
    qty_allocated, stock_after
)
PRIMARY KEY (request_id, provider_id)
```

**Anomaly removed:** the list-vs-list correspondence bug, and queries that
cannot filter on a repeated value.

**Still broken:** every request-level fact is now duplicated once per
allocation. A two-centre allocation stores `severity`, `urgency` and
`priority_score` twice, so they can disagree with each other within a single
request.

---

## 2. Second normal form — no partial dependencies

**Rule.** 1NF, and every non-prime attribute depends on the *whole* key, not
part of it.

The key is `(request_id, provider_id)`. Three groups of columns depend on only
half of it:

| Columns | Depend on | Which is |
|---|---|---|
| `zone_*`, `resource_*`, `qty_requested`, `severity`, `urgency`, `priority_score`, `status`, `requested_at` | `request_id` | half the key (F1) |
| `provider_name`, `provider_pincode`, `provider_city`, `provider_state`, `provider_phone` | `provider_id` | the other half (F4) |
| `qty_allocated` | both | correct (F6) |

**Anomalies this causes.**

- *Update:* a centre's phone number is stored once per allocation it has ever
  made. Changing it means touching every one of those rows.
- *Insert:* a centre that has supplied nothing has no row, so its phone number
  cannot be recorded. Likewise a request nobody has filled yet has no
  `provider_id`, so it cannot be stored without a `NULL` in half the primary
  key — which is not allowed.
- *Delete:* removing the last allocation from a centre erases the centre.

**Fix.** Split by determinant.

```
Requests(request_id PK, zone_name, zone_state, zone_population,
         resource_name, resource_unit, resource_category,
         qty_requested, severity, urgency, priority_score, status, requested_at)

Providers(provider_id PK, provider_name, provider_pincode,
          provider_city, provider_state, provider_phone)

Allocations(request_id, provider_id, qty_allocated)
            PRIMARY KEY (request_id, provider_id)
```

**Anomaly removed:** provider facts are stored once. A pending request now
exists on its own, with no allocation and no `NULL` in a key.

**Still broken:** `Requests` carries zone and resource facts that have nothing
to do with a request.

---

## 3. Third normal form — no transitive dependencies

**Rule.** 2NF, and no non-prime attribute depends on another non-prime
attribute.

### 3a. `Requests` → `Zones`

`request_id → zone_name → zone_state, zone_population` (F2 with F8). `zone_name`
is non-prime, so state and population are transitively dependent.

- *Update:* Assam's population is repeated across every request from that zone.
- *Delete:* delete the last request from a zone and the zone disappears.
- *Insert:* a newly declared disaster zone cannot be recorded before someone
  raises a request from it.

### 3b. `Requests` → `Resources`

`request_id → resource_name → resource_unit, resource_category` (F3 with F9).
Identical shape: the unit of measure for blankets is restated on every request
for blankets, and two rows can disagree about whether blankets are counted in
`units` or `packets`.

### 3c. `Providers` → postal area

`provider_id → provider_pincode → provider_city, provider_state` (F5). A
pincode determines its city and state, so city and state are transitively
dependent on the key.

**Fix for 3a and 3b.** Extract the entities.

```
Zones(zone_id PK, zone_name UNIQUE, state, population, region, risk_level)
Resources(resource_id PK, name UNIQUE, unit, category)
Requests(request_id PK, zone_id FK, resource_id FK,
         qty_requested, severity, urgency, priority_score, status, requested_at)
Providers(provider_id PK, name, pincode, city, state, phone, latitude, longitude)
Allocations(allocation_id PK, request_id FK, provider_id FK, resource_id FK,
            qty_allocated, allocated_at)
StockLevels(provider_id, resource_id, quantity, low_stock_threshold)
            PRIMARY KEY (provider_id, resource_id)        -- F7
```

**Anomalies removed:** a zone exists independently of its requests; a resource's
unit is stored exactly once; deleting history no longer deletes reference data.

### 3d. The transitive dependency the schema keeps on purpose

**3c is not decomposed.** Strict 3NF says extract
`PostalArea(pincode PK, city, state)` and have `Providers` reference it.

The shipped schema keeps `city` and `state` on `Providers`, for three reasons:

1. Search filters and groups by `city` and `state` on nearly every query; a
   join to a lookup table buys nothing because nothing else ever uses it.
2. `pincode` is `NULL`-able in the real data. A provider with no pincode has no
   row to join to, so the decomposition would *lose* city and state for exactly
   the rows most likely to be incomplete.
3. The anomaly it protects against — two providers with the same pincode in
   different cities — is a data-entry error in reference data that is loaded
   once from a deterministic seed, not something users type.

So the honest claim is: **the schema is in 3NF except for `Providers`, where one
transitive dependency is kept deliberately, documented here, with the anomaly it
admits stated.** That is a better viva answer than "yes, it's in 3NF", because
it shows the rule *and* the judgement.

Contrast this with the other denormalization in the schema,
`Requests.quantity_allocated`: that one is derived (`SUM` over `Allocations`)
rather than transitively dependent, and it is kept consistent by a trigger
rather than by hope. Two different problems, two different tools.

---

## 4. Boyce–Codd normal form

**Rule.** For every non-trivial dependency `X → Y`, `X` must be a superkey.
3NF forgives a violation when `Y` is *prime* (part of some candidate key);
BCNF does not.

Most tables here are trivially in BCNF: with a surrogate primary key and a
`UNIQUE` constraint on the natural key, both are candidate keys and every
determinant is one of them. `Zones`, `Resources`, `Providers`, `Requests`,
`Allocations` and `StockLevels` are all in this group.

### The one real case: `EmergencyContact`

```
EmergencyContact(name, region, number)
```

Two dependencies hold:

```
G1   (name, region) → number      -- Ambulance in Assam has one number
G2   number         → name        -- a number belongs to exactly one service
```

Candidate keys: `(name, region)` and `(number, region)`.

- **It is in 3NF.** G2's right-hand side, `name`, is prime — it is part of the
  candidate key `(name, region)` — and 3NF permits that.
- **It is not in BCNF.** G2's determinant, `number`, is not a superkey: knowing
  the number does not identify the row, because the same number can serve
  several regions.

The anomaly this admits is real but small: if `102` is stored for Assam and for
Odisha, and the service is renamed, one row can be updated and the other not,
leaving `102` meaning two different things.

**The BCNF decomposition:**

```
ContactNumber(number PK, name)
ContactCoverage(number FK, region)   PRIMARY KEY (number, region)
```

**The schema does not do this**, and the reason is the standard BCNF trade-off
rather than laziness. The decomposition is lossless but **not
dependency-preserving**: G1, `(name, region) → number`, spans both tables
afterwards, so "one number per service per region" can no longer be enforced by
a key — it needs a trigger or an application check. Trading a declarative
constraint for a procedural one, to protect six rows of hand-maintained
reference data against an anomaly nobody can trigger through the UI, is a bad
deal.

Being able to say *that* — lossless-join versus dependency preservation, and
which one you gave up — is the actual BCNF question an examiner is asking.

---

## 5. Verdict

| Table | Highest normal form | Note |
|---|---|---|
| `Zones` | BCNF | `zone_name` is `UNIQUE`, so it is a candidate key |
| `Resources` | BCNF | `name` is `UNIQUE` |
| `Requests` | BCNF | single candidate key, the surrogate |
| `Allocations` | BCNF | |
| `StockLevels` | BCNF | key `(provider_id, resource_id)`; nothing else determines anything |
| `StockThresholds` | BCNF | `resource_id` is `UNIQUE`, so both it and the surrogate are candidate keys |
| `ServiceCategory` | BCNF | `name` is `UNIQUE` |
| `ServicesOffered` | BCNF | `UNIQUE (provider_id, category_id)` |
| `StockHistory`, `AuditLog`, `UserQuery` | BCNF | append-only event rows; the surrogate key is the only determinant |
| `RiskScores`, `ZoneSummary`, `ResourceConsumptionRate` | BCNF *as relations* | but they are **materialised aggregates**: every column is derivable from base tables, so they are redundant by construction. Justified by read performance and kept correct by triggers, not by normalization. |
| `Providers` | **3NF, not BCNF** | the kept `pincode → city, state` of §3d |
| `EmergencyContact` | **3NF, not BCNF** | the kept `number → name` of §4 |

Two deliberate exceptions, both documented, both with the admitted anomaly
written down. Everything else reaches BCNF.

---

## 6. Viva questions this document answers

**Is your schema in 3NF? Is it in BCNF?**
BCNF everywhere except two tables. `Providers` keeps `pincode → city, state`
because the lookup table would be joined by nothing else and would lose data
for rows with a `NULL` pincode. `EmergencyContact` keeps `number → name`
because the BCNF decomposition is not dependency-preserving.

**What anomaly does each decomposition remove?**
1NF removes the list-correspondence bug. 2NF removes duplicated provider facts
and makes an unfilled request representable. 3NF removes duplicated zone and
resource facts, and stops deleting history from deleting reference data.

**Why is a denormalization ever acceptable?**
When the cost is known and the anomaly is prevented by something other than the
normal form. The schema has three, each with a different guard: `Providers.city`
(guarded by deterministic seed data), `Requests.quantity_allocated` (guarded by
a trigger), and the materialised aggregates (guarded by triggers, and acceptable
because they are rebuildable from base tables at any time).

**What is the difference between 3NF and BCNF?**
3NF allows a non-superkey determinant if what it determines is prime. BCNF does
not. `EmergencyContact` is exactly that gap: `number → name`, `name` is prime,
so 3NF is satisfied and BCNF is not.

**Why not always decompose to BCNF?**
Because BCNF decomposition is always lossless but not always
dependency-preserving. Losing a dependency means a constraint the database
could have enforced with a key now has to be enforced by a trigger or by the
application — which can be forgotten.
