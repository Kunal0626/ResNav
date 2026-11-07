#!/usr/bin/env python3
"""SQL test runner.

Each test is a pair of files in db/tests/sql/:

    NNN_name.sql        statements to run
    NNN_name.expected   the exact output they must produce

The database is reloaded from db/tests/fixture.sql before every test, so no
test can see another's writes and the order they run in cannot matter. That
is not a luxury: the Python suite does NOT do this, and as a result it starts
failing on its third consecutive run (docs/AUDIT.md, "Broken test isolation").

Negative tests are first class. A case whose .expected contains an ERROR line
passes only when the server raises that exact error -- same number, same
message. A guard that is supposed to reject something and instead stays quiet
is a failing test, not a passing one, which is how the Phase 1 capability
probe caught a missing privilege that would otherwise have looked fine.

Credentials are never handled here. run.sh has already written a 0600 MySQL
defaults file and passes its path in RESNAV_MYSQL_DEFAULTS_FILE, so there is
exactly one place in the repo that touches a password.

Usage:
    runner.py              run every test
    runner.py --update     rewrite .expected from actual output (review the diff!)
    runner.py <substring>  run only matching tests
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "sql"
FIXTURE = ROOT / "fixture.sql"

MYSQL = os.environ.get("RESNAV_MYSQL_BIN", "mysql")
DEFAULTS = os.environ.get("RESNAV_MYSQL_DEFAULTS_FILE", "")
DATABASE = os.environ.get("RESNAV_MYSQL_DB", "resnav")

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""


def run_sql(sql: str) -> str:
    """Run SQL and return stdout and stderr merged, so errors are comparable."""
    if not DEFAULTS:
        sys.exit("error: RESNAV_MYSQL_DEFAULTS_FILE is not set. Run via ./run.sh test.")
    # --force: the client keeps going after an error instead of abandoning
    # the file. A negative test that asserts four separate rejections needs
    # all four to actually be attempted, and an unexpected early failure is
    # still perfectly visible -- it shows up in the diff.
    proc = subprocess.run(
        [MYSQL, f"--defaults-extra-file={DEFAULTS}", "--force", DATABASE],
        input=sql, capture_output=True, text=True,
    )
    return proc.stdout + proc.stderr


def normalise(text: str) -> str:
    """Strip what legitimately varies between runs.

    Timestamps, auto-increment values that depend on history, and the client's
    own warning about passwords are not what any test is asserting. Everything
    else is compared literally -- including error numbers and messages.
    """
    out = []
    for line in text.splitlines():
        line = line.rstrip()
        if "Using a password on the command line" in line:
            continue
        # 2026-11-07 18:42:01.123456 -> <TIMESTAMP>
        line = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?", "<TIMESTAMP>", line)
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    update = "--update" in argv
    needles = [a for a in argv if not a.startswith("-")]

    cases = sorted(CASES.glob("*.sql"))
    if needles:
        cases = [c for c in cases if any(n in c.name for n in needles)]
    if not cases:
        print("no test cases found")
        return 1

    fixture_sql = FIXTURE.read_text()
    passed, failed, written = 0, 0, 0

    for case in cases:
        expected_path = case.with_suffix(".expected")

        # Reload the fixture first, and refuse to run if that itself failed --
        # otherwise the test reports a confusing mismatch instead of the real
        # problem.
        setup = run_sql(fixture_sql)
        if "ERROR" in setup:
            print(f"{RED}SETUP FAIL{RESET} {case.name}")
            print("\n".join("    " + l for l in setup.splitlines()[:5]))
            failed += 1
            continue

        actual = normalise(run_sql(case.read_text()))

        if update:
            expected_path.write_text(actual)
            print(f"{YELLOW}WROTE{RESET}     {case.name}")
            written += 1
            continue

        if not expected_path.exists():
            print(f"{RED}NO EXPECTED{RESET} {case.name} -- run with --update, then review")
            failed += 1
            continue

        expected = normalise(expected_path.read_text())
        if actual == expected:
            print(f"{GREEN}PASS{RESET}      {case.name}")
            passed += 1
        else:
            print(f"{RED}FAIL{RESET}      {case.name}")
            exp_lines, act_lines = expected.splitlines(), actual.splitlines()
            for i in range(max(len(exp_lines), len(act_lines))):
                e = exp_lines[i] if i < len(exp_lines) else "<missing>"
                a = act_lines[i] if i < len(act_lines) else "<missing>"
                if e != a:
                    print(f"    line {i + 1}")
                    print(f"      {DIM}expected{RESET} {e}")
                    print(f"      {DIM}actual  {RESET} {a}")
            failed += 1

    print()
    if update:
        print(f"{written} expectation file(s) written. Review the diff before committing.")
        return 0
    print(f"{passed} passed, {failed} failed, {len(cases)} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
