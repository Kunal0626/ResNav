"""Shared machinery for the concurrency experiments.

Every script here opens REAL, SEPARATE MySQL connections and drives them from
threads. Nothing is simulated: if a session blocks on a lock, this process
genuinely blocks, and if MySQL picks a deadlock victim it genuinely does.

Two details make the results trustworthy rather than anecdotal:

  * A `threading.Barrier` releases both sessions at the same instant, so the
    interleaving is forced rather than hoped for.
  * `think()` widens the gap between a read and the write that depends on it.
    That does not CREATE the race -- it makes a race that already exists
    reproducible instead of showing up once a week in production.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

REPO = Path(__file__).resolve().parents[3]


def _env() -> dict:
    # run.sh exports these from the one root .env. Reading them directly, and
    # never a password from a file of our own, keeps credential handling in
    # exactly one place.
    missing = [k for k in ("DRA_MYSQL_USER", "DRA_MYSQL_PASSWORD") if not os.environ.get(k)]
    if missing:
        sys.exit(f"error: {', '.join(missing)} not set. Run via ./run.sh concurrency.")
    return {
        "host": os.environ.get("DRA_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("DRA_MYSQL_PORT", "3306")),
        "user": os.environ["DRA_MYSQL_USER"],
        "password": os.environ["DRA_MYSQL_PASSWORD"],
        "database": os.environ.get("DRA_MYSQL_DB", "resnav"),
    }


def connect(isolation: str | None = None) -> pymysql.connections.Connection:
    conn = pymysql.connect(**_env(), charset="utf8mb4",
                           cursorclass=DictCursor, autocommit=False)
    if isolation:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation}")
    return conn


def one(conn, sql: str, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return row


def run(conn, sql: str, params=()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def think(seconds: float = 0.35) -> None:
    """Widen the window between a read and the write that depends on it."""
    time.sleep(seconds)


def scenario(title: str, question: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("-" * 78)
    print(question.strip())
    print()


def verdict(text: str) -> None:
    print()
    print(f"  >> {text}")


def two_sessions(work_a, work_b) -> tuple:
    """Run two callables against their own connections, released together."""
    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def wrap(name, fn):
        def inner():
            conn = connect()
            try:
                results[name] = fn(conn, barrier)
            # Broad on purpose: a deadlock victim, a lock-wait timeout and a
            # SIGNAL from a guard are all legitimate outcomes to report, and
            # letting any of them escape would kill the thread and lose the
            # other session's result too.
            except Exception as exc:  # noqa: BLE001
                results[name] = exc
            finally:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001,S110 - teardown must not mask the result
                    pass
        return inner

    ta = threading.Thread(target=wrap("A", work_a))
    tb = threading.Thread(target=wrap("B", work_b))
    ta.start(); tb.start()
    ta.join(timeout=60); tb.join(timeout=60)
    return results.get("A"), results.get("B")


def describe(exc_or_value) -> str:
    if isinstance(exc_or_value, BaseException):
        args = getattr(exc_or_value, "args", ())
        if len(args) >= 2:
            return f"ERROR {args[0]}: {str(args[1])[:72]}"
        return f"{type(exc_or_value).__name__}: {exc_or_value}"
    return str(exc_or_value)


def reset_fixture() -> None:
    """Reload the tiny hand-checkable set, so every experiment starts from the
    same three centres with 10 / 40 / 100 blankets."""
    sql = (REPO / "db" / "tests" / "fixture.sql").read_text()
    conn = connect()
    try:
        for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
            if stmt.startswith("--"):
                stmt = "\n".join(line for line in stmt.splitlines()
                                 if not line.strip().startswith("--")).strip()
            if stmt:
                run(conn, stmt)
        conn.commit()
    finally:
        conn.close()


def stock(resource_id: int = 1) -> list[tuple[int, float]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT provider_id, quantity FROM StockLevels "
                        "WHERE resource_id = %s ORDER BY provider_id", (resource_id,))
            return [(r["provider_id"], float(r["quantity"])) for r in cur.fetchall()]
    finally:
        conn.close()
