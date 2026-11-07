#!/usr/bin/env python3
"""EXPERIMENT 3 -- the same race, through sp_allocate_request.

Identical setup to experiment 2: ten units in the whole system, two requests
that each want all ten, fired simultaneously. The only change is that the
decision happens inside the database, behind locks taken in primary-key
order, with the quantities re-read after the locks are held.
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
    two_sessions,
    verdict,
)


def allocator(request_id: int):
    def work(conn, barrier):
        barrier.wait()
        with conn.cursor() as cur:
            cur.execute("CALL sp_allocate_request(%s, 0, @a, @l, @s)", (request_id,))
            while cur.nextset():
                pass
            cur.execute("SELECT @a AS allocated, @l AS legs, @s AS status")
            out = cur.fetchone()
        conn.commit()
        return f"allocated {float(out['allocated'] or 0)}, legs {out['legs']}, status {out['status']}"
    return work


def main() -> int:
    scenario("EXPERIMENT 3 -- the same race, through sp_allocate_request",
             """Ten units exist in the entire system. Two requests each ask for all ten,
fired at the same instant. Correct outcome: between them they receive
exactly ten, with no error and no negative stock.""")

    reset_fixture()
    conn = connect()
    # Leave stock ONLY at centre 1, so both requests must contend for the
    # same row. With stock spread across three centres they would simply be
    # served from different ones and nothing would be proved.
    run(conn, "UPDATE StockLevels SET quantity = 0 WHERE resource_id = 1 AND provider_id IN (2, 3)")
    for rid in (811, 812):
        run(conn, "INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, "
                  "severity, urgency) VALUES (%s, 1, 1, 10, 2, 2)", (rid,))
    conn.commit()

    print(f"  stock before: {stock()}  (total 10)")
    a, b = two_sessions(allocator(811), allocator(812))
    print(f"  session A: {describe(a)}")
    print(f"  session B: {describe(b)}")

    after = stock()
    total_left = sum(q for _p, q in after)
    handed_out = 10 - total_left
    print(f"\n  stock after: {after}")

    allocated = one(conn, "SELECT COALESCE(SUM(quantity_allocated), 0) AS n FROM Allocations "
                          "WHERE status = 'active' AND request_id IN (811, 812)")
    print(f"  units handed out: {handed_out}")
    print(f"  sum of active allocations: {float(allocated['n'])}")

    errors = [r for r in (a, b) if isinstance(r, BaseException)]
    negative = [p for p, q in after if q < 0]

    if negative:
        verdict(f"FAILED -- stock went negative at {negative}.")
    elif errors:
        verdict(f"FAILED -- a session errored: {describe(errors[0])}")
    elif handed_out == 10 == float(allocated["n"]):
        verdict("CORRECT. Exactly ten units were handed out, the allocations sum "
                "to the same ten, neither session errored, and the second "
                "request simply received nothing because there was nothing "
                "left. The lock made one session wait rather than fail.")
    else:
        verdict(f"Unexpected: handed out {handed_out}, allocations {float(allocated['n'])}.")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
