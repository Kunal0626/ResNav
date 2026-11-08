#!/usr/bin/env python3
"""Measure this project, so the README can quote numbers instead of adjectives.

Everything printed here was produced by running the thing. Each measurement
records the machine, the server version and the data size next to it, because
a latency figure without those is a decoration.

What it measures, and why each one:

  allocation      sp_allocate_request end to end -- the operation the whole
                  project exists to perform. Reported as a distribution, not
                  a mean: a mean hides the tail, and the tail is where lock
                  contention lives.
  index           the allocator's candidate lookup, with and without
                  ix_stocklevels_resource_provider, including the plan the
                  optimiser actually chose. Dropping an index to measure it
                  is the only honest way to claim it helped.
  function        fn_haversine_km on its own, so its cost can be separated
                  from the query that calls it.
  reads           the views the API serves from.

Usage:  ./run.sh bench            all of it
        ./run.sh bench --json     machine-readable, for diffing between runs
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

REPO = Path(__file__).resolve().parent.parent


def connect(autocommit: bool = True):
    missing = [k for k in ("DRA_MYSQL_USER", "DRA_MYSQL_PASSWORD") if not os.environ.get(k)]
    if missing:
        sys.exit(f"error: {', '.join(missing)} not set. Run via ./run.sh bench.")
    return pymysql.connect(
        host=os.environ.get("DRA_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("DRA_MYSQL_PORT", "3306")),
        user=os.environ["DRA_MYSQL_USER"],
        password=os.environ["DRA_MYSQL_PASSWORD"],
        database=os.environ.get("DRA_MYSQL_DB", "resnav"),
        charset="utf8mb4", cursorclass=DictCursor, autocommit=autocommit,
    )


def q(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def one(conn, sql, params=()):
    rows = q(conn, sql, params)
    return rows[0] if rows else None


def stats(samples_ms: list[float]) -> dict:
    s = sorted(samples_ms)
    n = len(s)
    pct = lambda p: s[min(n - 1, round(p / 100 * n) - 1 if p < 100 else n - 1)]
    return {
        "n": n,
        "min_ms": round(s[0], 3),
        "p50_ms": round(statistics.median(s), 3),
        "p95_ms": round(pct(95), 3),
        "p99_ms": round(pct(99), 3),
        "max_ms": round(s[-1], 3),
        "mean_ms": round(statistics.fmean(s), 3),
    }


def environment(conn) -> dict:
    v = one(conn, "SELECT VERSION() AS v")["v"]
    sizes = one(conn, """
        SELECT (SELECT COUNT(*) FROM Providers)   AS providers,
               (SELECT COUNT(*) FROM Resources)   AS resources,
               (SELECT COUNT(*) FROM Zones)       AS zones,
               (SELECT COUNT(*) FROM StockLevels) AS stock_rows,
               (SELECT COUNT(*) FROM Requests)    AS requests,
               (SELECT COUNT(*) FROM StockHistory) AS history_rows""")
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True, check=False).stdout.strip()
    except Exception:  # noqa: BLE001 - the CPU name is decoration, not data
        cpu = ""
    return {
        "mysql": v,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "cpu": cpu or platform.processor(),
        "data": sizes,
    }


# ── allocation ──────────────────────────────────────────────────────────────

def bench_allocation(conn, runs: int) -> dict:
    """Time sp_allocate_request on freshly created requests.

    Each iteration creates its own request, so no two measurements contend
    for the same row and none of them is timing a no-op against a request
    that is already fulfilled.
    """
    zone = one(conn, "SELECT id, zone_name FROM Zones ORDER BY id LIMIT 1")
    resource = one(conn, """
        SELECT sl.resource_id AS id, r.name
        FROM StockLevels sl JOIN Resources r ON r.id = sl.resource_id
        GROUP BY sl.resource_id, r.name
        HAVING SUM(sl.quantity) > 2000
        ORDER BY SUM(sl.quantity) DESC LIMIT 1""")
    if not resource:
        return {"skipped": "no resource holds enough stock for a repeated "
                           "allocation benchmark; run `make reset` first"}

    samples, legs_seen, allocated_total = [], [], 0.0
    with conn.cursor() as cur:
        for _ in range(runs):
            cur.execute("""
                INSERT INTO Requests (zone_id, resource_id, quantity_requested,
                                      severity, urgency, population_affected)
                VALUES (%s, %s, 25, 2.0, 2.0, 1000)""", (zone["id"], resource["id"]))
            rid = cur.lastrowid

            start = time.perf_counter()
            cur.execute("CALL sp_allocate_request(%s, 0, @a, @l, @s)", (rid,))
            while cur.nextset():
                pass
            samples.append((time.perf_counter() - start) * 1000)

            cur.execute("SELECT @a AS allocated, @l AS legs")
            out = cur.fetchone()
            legs_seen.append(int(out["legs"] or 0))
            allocated_total += float(out["allocated"] or 0)

    return {
        "what": f"CALL sp_allocate_request -- 25 units of {resource['name']} "
                f"for {zone['zone_name']}",
        "latency": stats(samples),
        "throughput_per_sec": round(1000 / statistics.median(samples), 1),
        "median_legs": statistics.median(legs_seen),
        "units_allocated": round(allocated_total, 1),
    }


# ── the index ───────────────────────────────────────────────────────────────

CANDIDATE_SQL = """
    SELECT sl.provider_id, sl.quantity
      FROM StockLevels sl
      JOIN Providers p ON p.id = sl.provider_id
     WHERE sl.resource_id = %s AND sl.quantity > 0
     ORDER BY fn_haversine_km(%s, %s, p.latitude, p.longitude)
"""


def plan_for(conn, sql: str, params) -> dict:
    """Capture the query plan, in both shapes MySQL offers.

    MySQL 8.0.16+ defaults EXPLAIN to TREE format -- one text column, not
    the classic table -- which is why a parser written against `key` and
    `rows` silently returns nothing. The tree is the better artefact to put
    in documentation, so it is kept verbatim; FORMAT=TRADITIONAL is read
    alongside it for the fields worth comparing in a table.
    """
    tree = "\n".join(
        str(next(iter(r.values()))) for r in q(conn, "EXPLAIN FORMAT=TREE " + sql, params)
    ).strip()
    rows = q(conn, "EXPLAIN FORMAT=TRADITIONAL " + sql, params)
    chosen = next((r for r in rows if r.get("table") in ("sl", "StockLevels")), rows[0] if rows else {})

    access = "unknown"
    for line in tree.splitlines():
        line = line.strip()
        if "on sl" in line or "on StockLevels" in line:
            access = re.sub(r"\s+\(cost=.*$", "", line.lstrip("-> ")).strip()
            break

    return {
        "access": access,
        "tree": tree,
        "type": chosen.get("type"),
        "key": chosen.get("key"),
        "rows_estimated": chosen.get("rows"),
        "extra": chosen.get("Extra"),
    }


def timed(conn, sql, params, runs: int) -> list[float]:
    out = []
    for _ in range(runs):
        start = time.perf_counter()
        q(conn, sql, params)
        out.append((time.perf_counter() - start) * 1000)
    return out


def bench_index(conn, runs: int) -> dict:
    """The allocator's lookup, with and without its index.

    StockLevels has PRIMARY KEY (provider_id, resource_id) and a secondary
    index the other way round. A composite index only answers a lookup that
    fixes a LEFTMOST PREFIX of its columns, so the primary key cannot serve
    "which providers hold resource 12" -- the allocator's question on every
    single run.

    The comparison is made with IGNORE INDEX rather than by dropping the
    index, and not for convenience: THE INDEX CANNOT BE DROPPED. InnoDB
    requires an index whose leftmost column is the referencing column of a
    foreign key, and fk_stocklevels_resource is on resource_id -- which this
    index happens to lead with. MySQL refuses the drop with

        ERROR 1553: Cannot drop index '...': needed in a foreign key constraint

    So the index is not an optimisation the schema could choose to omit; it
    is load-bearing twice over, and the query planner was always going to
    have it. IGNORE INDEX gives the honest read-path comparison: the plan
    the optimiser produces when it may not use that index. The index still
    exists, so this measures the READ benefit only and says nothing about
    its write cost.
    """
    zone = one(conn, "SELECT latitude, longitude FROM Zones ORDER BY id LIMIT 1")
    resource = one(conn, "SELECT resource_id AS id FROM StockLevels "
                         "GROUP BY resource_id ORDER BY COUNT(*) DESC LIMIT 1")
    args = (resource["id"], zone["latitude"], zone["longitude"])

    ignored_sql = CANDIDATE_SQL.replace(
        "FROM StockLevels sl",
        "FROM StockLevels sl IGNORE INDEX (ix_stocklevels_resource_provider)")

    after_plan = plan_for(conn, CANDIDATE_SQL, args)
    after = timed(conn, CANDIDATE_SQL, args, runs)
    before_plan = plan_for(conn, ignored_sql, args)
    before = timed(conn, ignored_sql, args, runs)

    return {
        "what": "candidate lookup: which centres hold resource X, nearest first",
        "method": "IGNORE INDEX -- the index cannot be dropped, "
                  "fk_stocklevels_resource requires it (MySQL error 1553)",
        "without_index": {"plan": before_plan, "latency": stats(before)},
        "with_index": {"plan": after_plan, "latency": stats(after)},
        "speedup": round(statistics.median(before) / statistics.median(after), 2),
    }


def bench_index_at_scale(conn, rows: int, runs: int) -> dict:
    """Where the index actually starts to matter.

    On the seed it does not: 30 centres and 596 stock rows are small enough
    that the optimiser just reverses the join and does a primary-key lookup
    per provider, and both plans land within noise of each other. Reporting
    a speedup from that would be inventing one.

    So this builds a scratch table with the same shape and a realistic
    number of rows, and measures there. The scratch table has no foreign
    keys, which means the index CAN be dropped -- the real comparison the
    production table would not allow. It is synthetic and says so; what it
    shows is the size at which the leftmost-prefix rule stops being a
    technicality.
    """
    conn.query("DROP TABLE IF EXISTS bench_stock")
    conn.query("""
        CREATE TABLE bench_stock (
            provider_id INT UNSIGNED      NOT NULL,
            resource_id SMALLINT UNSIGNED NOT NULL,
            quantity    DECIMAL(12,3)     NOT NULL,
            PRIMARY KEY (provider_id, resource_id)
        ) ENGINE=InnoDB""")

    # Generated server-side from a recursive CTE: moving 200k rows over the
    # wire would measure the client, not the database. The recursion limit
    # defaults to 1000, which is a guard against a runaway CTE rather than a
    # capacity limit, so it is raised for this session only.
    conn.query(f"SET SESSION cte_max_recursion_depth = {rows + 10}")
    conn.query(f"""
        INSERT INTO bench_stock (provider_id, resource_id, quantity)
        WITH RECURSIVE seq(n) AS (
            SELECT 0 UNION ALL SELECT n + 1 FROM seq WHERE n < {rows - 1}
        )
        SELECT (n DIV 500) + 1, (n MOD 500) + 1, (n MOD 997)
        FROM seq""")
    conn.query("ANALYZE TABLE bench_stock")

    sql = "SELECT provider_id, quantity FROM bench_stock WHERE resource_id = %s AND quantity > 0"
    args = (123,)

    without_plan = plan_for_table(conn, sql, args, "bench_stock")
    without = timed(conn, sql, args, runs)

    conn.query("ALTER TABLE bench_stock ADD INDEX ix_bench (resource_id, provider_id)")
    conn.query("ANALYZE TABLE bench_stock")
    with_plan = plan_for_table(conn, sql, args, "bench_stock")
    with_idx = timed(conn, sql, args, runs)

    actual = one(conn, "SELECT COUNT(*) AS n FROM bench_stock")["n"]
    conn.query("DROP TABLE IF EXISTS bench_stock")

    return {
        "what": f"same lookup shape on a synthetic table of {actual:,} rows",
        "rows": actual,
        "without_index": {"plan": without_plan, "latency": stats(without)},
        "with_index": {"plan": with_plan, "latency": stats(with_idx)},
        "speedup": round(statistics.median(without) / statistics.median(with_idx), 1),
    }


def plan_for_table(conn, sql: str, params, table: str) -> dict:
    tree = "\n".join(
        str(next(iter(r.values()))) for r in q(conn, "EXPLAIN FORMAT=TREE " + sql, params)
    ).strip()
    rows = q(conn, "EXPLAIN FORMAT=TRADITIONAL " + sql, params)
    chosen = rows[0] if rows else {}
    access = "unknown"
    for line in tree.splitlines():
        line = line.strip()
        if table in line:
            access = re.sub(r"\s+\(cost=.*$", "", line.lstrip("-> ")).strip()
            break
    return {"access": access, "tree": tree, "type": chosen.get("type"),
            "key": chosen.get("key"), "rows_estimated": chosen.get("rows")}


# ── function and reads ──────────────────────────────────────────────────────

def bench_function(conn, runs: int) -> dict:
    sql = "SELECT fn_haversine_km(26.144500, 91.736200, 13.082700, 80.270700) AS km"
    return {"what": "fn_haversine_km, one call", "latency": stats(timed(conn, sql, (), runs))}


def bench_reads(conn, runs: int) -> dict:
    out = {}
    for name, sql in [
        ("v_center_stock_summary", "SELECT * FROM v_center_stock_summary"),
        ("v_request_fulfilment",   "SELECT * FROM v_request_fulfilment"),
        ("v_provider_reliability", "SELECT * FROM v_provider_reliability"),
        ("v_zone_shortage_analysis", "SELECT * FROM v_zone_shortage_analysis"),
    ]:
        rows = len(q(conn, sql))
        out[name] = {"rows": rows, "latency": stats(timed(conn, sql, (), runs))}
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=60)
    ap.add_argument("--scale", type=int, default=200_000,
                    help="rows in the synthetic index-scale table")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    conn = connect()
    report = {"environment": environment(conn)}
    report["allocation"] = bench_allocation(conn, args.runs)
    report["index"] = bench_index(conn, max(args.runs, 100))
    report["index_at_scale"] = bench_index_at_scale(conn, args.scale, max(args.runs, 100))
    report["function"] = bench_function(conn, max(args.runs, 200))
    report["reads"] = bench_reads(conn, args.runs)
    conn.close()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    env = report["environment"]
    print("=" * 74)
    print("ResNav measurements")
    print("=" * 74)
    print(f"  MySQL     {env['mysql']}")
    print(f"  Python    {env['python']}")
    print(f"  Platform  {env['platform']}")
    print(f"  CPU       {env['cpu']}")
    d = env["data"]
    print(f"  Data      {d['providers']} centres, {d['resources']} resources, "
          f"{d['stock_rows']} stock rows, {d['requests']} requests, "
          f"{d['history_rows']} history rows")

    a = report["allocation"]
    if "skipped" in a:
        print(f"\nallocation: skipped -- {a['skipped']}")
    else:
        lat = a["latency"]
        print("\n-- allocation ----------------------------------------------")
        print(f"  {a['what']}")
        print(f"  n={lat['n']}  p50 {lat['p50_ms']} ms   p95 {lat['p95_ms']} ms   "
              f"p99 {lat['p99_ms']} ms   max {lat['max_ms']} ms")
        print(f"  {a['throughput_per_sec']} allocations/sec at the median, "
              f"single session, median {a['median_legs']} leg(s) each")

    i = report["index"]
    print("\n-- index: ix_stocklevels_resource_provider -----------------")
    print(f"  {i['what']}")
    print(f"  method: {i['method']}")
    for label, key in (("WITHOUT the index", "without_index"), ("WITH the index", "with_index")):
        pl, lat = i[key]["plan"], i[key]["latency"]
        print(f"\n  {label}")
        print(f"    access          {pl['access']}")
        print(f"    type={pl['type']}  key={pl['key']}  rows_estimated={pl['rows_estimated']}")
        print(f"    p50 {lat['p50_ms']} ms   p95 {lat['p95_ms']} ms")
    print(f"\n  rows estimated   {i['without_index']['plan']['rows_estimated']}"
          f" -> {i['with_index']['plan']['rows_estimated']}")
    print(f"  median wall clock {i['speedup']}x")

    sc = report["index_at_scale"]
    print("\n-- index at scale ------------------------------------------")
    print(f"  {sc['what']}")
    for label, key in (("WITHOUT the index", "without_index"), ("WITH the index", "with_index")):
        pl, lat = sc[key]["plan"], sc[key]["latency"]
        print(f"\n  {label}")
        print(f"    access          {pl['access']}")
        print(f"    type={pl['type']}  key={pl['key']}  rows_estimated={pl['rows_estimated']}")
        print(f"    p50 {lat['p50_ms']} ms   p95 {lat['p95_ms']} ms")
    print(f"\n  median wall clock {sc['speedup']}x faster with the index")

    f = report["function"]["latency"]
    print("\n-- fn_haversine_km -----------------------------------------")
    print(f"  n={f['n']}  p50 {f['p50_ms']} ms   p95 {f['p95_ms']} ms")

    print("\n-- views ---------------------------------------------------")
    for name, r in report["reads"].items():
        print(f"  {name:<26} {r['rows']:>5} rows   p50 {r['latency']['p50_ms']} ms   "
              f"p95 {r['latency']['p95_ms']} ms")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
