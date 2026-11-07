#!/usr/bin/env python3
"""Run every concurrency experiment in order and report.

Each script is a separate process, so one wedged connection cannot poison
the next experiment. Output is printed as it is produced; docs/CONCURRENCY.md
is written from this output and nothing else.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCRIPTS = [
    ("c01_oversell_unguarded.py", "the bug, with nothing in the way"),
    ("c02_race_with_triggers.py", "real schema, application-side read-then-write"),
    ("c03_real_allocator.py",     "the same race through sp_allocate_request"),
    ("c04_isolation_levels.py",   "what the isolation level actually changes"),
    ("c05_deadlock.py",           "a deadlock, and the ordering that prevents it"),
    ("c06_http_api.py",           "the same race over HTTP"),
]


def main(argv: list[str]) -> int:
    only = [a for a in argv if not a.startswith("-")]
    failures = []
    for name, summary in SCRIPTS:
        if only and not any(o in name for o in only):
            continue
        # check=False: two of these experiments are SUPPOSED to demonstrate
        # failure, so a non-zero exit is reported, not raised.
        proc = subprocess.run([sys.executable, "-I", str(HERE / name)], check=False)
        if proc.returncode != 0:
            failures.append(name)

    print()
    print("=" * 78)
    if failures:
        print(f"{len(failures)} experiment(s) exited non-zero: {', '.join(failures)}")
        return 1
    print("All experiments ran. Read the verdicts above -- an experiment that")
    print("RUNS is not the same as an experiment that PASSED, and two of these")
    print("are supposed to demonstrate failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
