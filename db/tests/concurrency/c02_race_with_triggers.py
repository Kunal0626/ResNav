#!/usr/bin/env python3
"""EXPERIMENT 2 -- the real schema, but the application does its own
read-then-write instead of calling sp_allocate_request.

This is what the SQLite code looked like, ported straight across. The
invariants hold -- the trigger and the CHECK see to that -- so stock cannot
go negative. The question is whether that makes the system CORRECT, or
merely unable to become corrupt.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (
    connect,
    describe,
    one,
    reset_fixture,
    run,
    scenario,
    stock,
    think,
    two_sessions,
    verdict,
)


def naive_allocator(request_id: int, units: float):
    """Read the balance, decide, then write -- with no lock held across the gap."""
    def work(conn, barrier):
        barrier.wait()
        row = one(conn, "SELECT quantity FROM StockLevels "
                        "WHERE provider_id = 1 AND resource_id = 1")
        seen = float(row["quantity"])

        think()

        if seen < units:
            return f"read {seen}, declined to allocate {units}"
        conn.begin()
        run(conn, "INSERT INTO Allocations (request_id, provider_id, resource_id, "
                  "quantity_allocated) VALUES (%s, 1, 1, %s)", (request_id, units))
        conn.commit()
        return f"read {seen}, allocated {units}"
    return work


def main() -> int:
    scenario("EXPERIMENT 2 -- real schema, application-side read-then-write",
             """Centre 1 holds exactly 10 blankets. Two requests each ask for all 10,
and the application checks availability itself before inserting.
Correct outcome: one allocation succeeds, one is declined cleanly.""")

    reset_fixture()
    conn = connect()
    for rid in (801, 802):
        run(conn, "INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, "
                  "severity, urgency) VALUES (%s, 1, 1, 10, 2, 2)", (rid,))
    conn.commit()

    print(f"  stock before: {stock()}")
    a, b = two_sessions(naive_allocator(801, 10), naive_allocator(802, 10))
    print(f"  session A: {describe(a)}")
    print(f"  session B: {describe(b)}")
    after = stock()
    print(f"\n  stock after: {after}")

    negative = [p for p, q in after if q < 0]
    errors = [r for r in (a, b) if isinstance(r, BaseException)]

    if negative:
        verdict(f"Stock went NEGATIVE at provider(s) {negative} -- the invariant failed.")
    elif errors:
        verdict("No oversell: stock never went negative, because the trigger "
                "refused the second write. But the refusal arrived as "
                f"{describe(errors[0])} -- an unhandled database error, after the "
                "user was already told the dispatch was possible. The data is "
                "intact; the system is not reliable.")
    else:
        verdict("Both sessions completed without error in this run.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
