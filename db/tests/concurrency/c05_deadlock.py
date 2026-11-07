#!/usr/bin/env python3
"""EXPERIMENT 5 -- causing a deadlock on purpose, then making it impossible.

A deadlock is not a database fault. It is two transactions each holding a
lock the other needs, which is a property of the ORDER they took them in.
Change the order and the deadlock cannot occur -- no retry loop required.

Part A locks two rows in opposite orders. Part B locks the same two rows in
the same order. Nothing else differs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import describe, reset_fixture, run, scenario, two_sessions, verdict


def locker(first: int, second: int, label: str, rendezvous: bool):
    """Lock provider `first`'s stock row, then reach for `second`.

    `rendezvous` is only safe when the two sessions take DIFFERENT first
    rows. With the same first row the second session blocks on it and never
    reaches the barrier, so the barrier itself deadlocks -- in Python, not in
    MySQL, and the symptom is a lock wait timeout that looks like a database
    result but is an artefact of the test. Part B therefore runs without it.
    """
    def work(conn, barrier):
        conn.begin()
        # Keep a failing wait short: the server default is 50 seconds, which
        # is a long time to sit watching a test that has already told you
        # what it is going to say.
        run(conn, "SET SESSION innodb_lock_wait_timeout = 5")
        run(conn, "SELECT quantity FROM StockLevels "
                  "WHERE provider_id = %s AND resource_id = 1 FOR UPDATE", (first,))
        if rendezvous:
            # Both sessions now hold one lock each. Only then do they reach
            # for the second -- otherwise one simply finishes first and there
            # is nothing to deadlock over.
            barrier.wait()
        try:
            run(conn, "SELECT quantity FROM StockLevels "
                      "WHERE provider_id = %s AND resource_id = 1 FOR UPDATE", (second,))
            conn.commit()
            return f"{label}: locked {first} then {second} -- committed"
        except Exception:
            conn.rollback()
            raise
    return work


def main() -> int:
    scenario("EXPERIMENT 5 -- a deadlock, and the ordering that prevents it",
             """Two sessions, two rows (centres 1 and 2), both needing both locks.
Part A takes them in opposite orders. Part B takes them in the same order.""")

    reset_fixture()

    print("  PART A -- opposite orders: session A takes 1 then 2, session B takes 2 then 1")
    a, b = two_sessions(locker(1, 2, "A", True), locker(2, 1, "B", True))
    print(f"    session A: {describe(a)}")
    print(f"    session B: {describe(b)}")
    victims = [r for r in (a, b) if isinstance(r, BaseException)
               and getattr(r, "args", [None])[0] == 1213]
    if victims:
        print(f"\n    MySQL chose a victim and rolled it back: {describe(victims[0])}")
    deadlocked = bool(victims)

    print()
    print("  PART B -- same order: both sessions take 1 then 2")
    reset_fixture()
    c, d = two_sessions(locker(1, 2, "A", False), locker(1, 2, "B", False))
    print(f"    session A: {describe(c)}")
    print(f"    session B: {describe(d)}")
    errors = [r for r in (c, d) if isinstance(r, BaseException)]

    print()
    if deadlocked and not errors:
        verdict("Opposite orders deadlocked and one transaction was rolled back "
                "with error 1213. The same order did not deadlock: one session "
                "simply waited for the other and both committed. "
                "sp_allocate_request always locks by (provider_id, resource_id), "
                "which is why it cannot reach part A's state.")
    elif not deadlocked:
        verdict("No deadlock was produced in part A on this run -- the timing "
                "did not interleave. Re-run; nothing is concluded from this.")
    else:
        verdict(f"Part B also errored: {describe(errors[0])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
