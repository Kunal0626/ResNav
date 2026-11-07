#!/usr/bin/env python3
"""EXPERIMENT 1 -- the bug, with nothing in the way.

A scratch table with no CHECK constraint, no trigger and no locking, so
nothing can save the application from itself. Two sessions each read the
same balance, each decide 10 units are available, and each write back what
they computed.

This is the baseline. Everything after it is measured against this.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import connect, describe, one, run, scenario, think, two_sessions, verdict

SETUP = """
DROP TABLE IF EXISTS race_scratch;
CREATE TABLE race_scratch (
    id       INT PRIMARY KEY,
    quantity INT NOT NULL
) ENGINE=InnoDB;
INSERT INTO race_scratch VALUES (1, 10);
"""


def taker(units: int):
    def work(conn, barrier):
        barrier.wait()
        # READ: how much is there?
        row = one(conn, "SELECT quantity FROM race_scratch WHERE id = 1")
        seen = int(row["quantity"])

        think()  # the window every such bug lives in

        # DECIDE and WRITE, against the number read before the window.
        if seen >= units:
            run(conn, "UPDATE race_scratch SET quantity = %s WHERE id = 1", (seen - units,))
            conn.commit()
            return f"read {seen}, took {units}, wrote {seen - units}"
        conn.rollback()
        return f"read {seen}, refused"
    return work


def main() -> int:
    scenario("EXPERIMENT 1 -- no constraint, no trigger, no lock",
             """Stock starts at 10. Two sessions each want 10 units.
Correct outcome: one succeeds, the other is refused. Total taken: 10.""")

    conn = connect()
    for stmt in [s.strip() for s in SETUP.split(";") if s.strip()]:
        run(conn, stmt)
    conn.commit()

    a, b = two_sessions(taker(10), taker(10))
    print(f"  session A: {describe(a)}")
    print(f"  session B: {describe(b)}")

    final = int(one(conn, "SELECT quantity FROM race_scratch WHERE id = 1")["quantity"])
    print(f"\n  stock afterwards: {final}")
    print(f"  units handed out: {10 - final}")

    oversold = (10 - final) < 20 and "took" in describe(a) and "took" in describe(b)
    if oversold:
        verdict(f"OVERSOLD. Both sessions believed they had 10 units and both "
                f"took 10, but the stock only fell by {10 - final}. "
                f"20 units were promised and 10 exist.")
    else:
        verdict("No oversell observed in this run.")

    run(conn, "DROP TABLE IF EXISTS race_scratch")
    conn.commit()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
