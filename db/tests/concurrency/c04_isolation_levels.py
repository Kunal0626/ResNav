#!/usr/bin/env python3
"""EXPERIMENT 4 -- what the isolation level actually changes.

One session reads a value, waits, and reads it again inside the SAME
transaction. Meanwhile another session changes it and commits.

Whether the second read sees the new value is decided entirely by the
isolation level, and it is the difference between "my plan is still valid"
and "my plan was valid when I made it".
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import connect, one, reset_fixture, run, scenario, verdict

LEVELS = ["READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]


def trial(level: str) -> dict:
    reset_fixture()
    result: dict = {"level": level}
    gate_read = threading.Event()
    gate_written = threading.Event()

    def reader():
        conn = connect(level)
        try:
            conn.begin()
            first = float(one(conn, "SELECT quantity FROM StockLevels "
                                    "WHERE provider_id = 1 AND resource_id = 1")["quantity"])
            result["first_read"] = first
            gate_read.set()
            gate_written.wait(timeout=20)
            second = float(one(conn, "SELECT quantity FROM StockLevels "
                                     "WHERE provider_id = 1 AND resource_id = 1")["quantity"])
            result["second_read"] = second
            conn.commit()
        # Broad on purpose: in a concurrency experiment the exception IS the
        # observation. SERIALIZABLE in particular may refuse the read outright,
        # and that outcome belongs in the results table, not in a traceback.
        except Exception as exc:  # noqa: BLE001
            result["reader_error"] = exc
            conn.rollback()
        finally:
            conn.close()

    def writer():
        conn = connect(level)
        try:
            gate_read.wait(timeout=20)
            time.sleep(0.1)
            conn.begin()
            run(conn, "UPDATE StockLevels SET quantity = 999 "
                      "WHERE provider_id = 1 AND resource_id = 1")
            conn.commit()
            result["write"] = "committed 999"
        except Exception as exc:  # noqa: BLE001 - the error is the result
            result["write"] = exc
        finally:
            gate_written.set()
            conn.close()

    tr = threading.Thread(target=reader)
    tw = threading.Thread(target=writer)
    tr.start(); tw.start()
    tr.join(timeout=40); tw.join(timeout=40)
    return result


def main() -> int:
    scenario("EXPERIMENT 4 -- isolation levels and the repeated read",
             """Session A reads centre 1's stock, waits, and reads it again inside one
transaction. Session B sets it to 999 and commits in between.
The question: does A's second read see 999?""")

    print(f"  {'isolation level':<18} {'1st read':>9} {'2nd read':>9}   what the writer did")
    print("  " + "-" * 74)
    rows = []
    for level in LEVELS:
        r = trial(level)
        rows.append(r)
        w = r.get("write")
        w_text = (f"ERROR {w.args[0]}: {str(w.args[1])[:34]}"
                  if isinstance(w, BaseException) else str(w))
        second = r.get("second_read")
        second_text = "error" if "reader_error" in r else f"{second}"
        print(f"  {level:<18} {r.get('first_read'):>9} {second_text:>9}   {w_text}")

    print()
    for r in rows:
        if "reader_error" in r:
            continue
        changed = r.get("first_read") != r.get("second_read")
        print(f"  {r['level']:<18} second read {'CHANGED' if changed else 'unchanged'} "
              f"-> {'non-repeatable read' if changed else 'snapshot held'}")

    verdict("The level decides whether a value you already read can move under "
            "you mid-transaction. Note that NONE of them stops the oversell on "
            "its own: a snapshot that cannot change still goes stale the moment "
            "the transaction commits. Only a lock held across the read and the "
            "write prevents it, which is what sp_allocate_request takes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
