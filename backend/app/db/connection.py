"""SQLite connection management.

One connection per request, stored on Flask's `g` and closed on teardown. The
old code opened and closed a connection inside every handler — a dozen
`try/finally` blocks per module and no way to share a transaction across helpers.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from flask import g

from ..core.config import get_settings

log = logging.getLogger(__name__)

_PRAGMAS = (
    "PRAGMA foreign_keys = ON",
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA temp_store = MEMORY",
    # ~64 MB page cache. The previous 30 GB mmap_size was cargo-culted; on a
    # 500 KB database it does nothing but reserve address space.
    "PRAGMA cache_size = -64000",
    "PRAGMA busy_timeout = 5000",
)


def connect(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a tuned connection. Callers outside a request context use this directly."""
    path = Path(database_path or get_settings().database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn


def get_db() -> sqlite3.Connection:
    """The current request's connection, opening one on first use."""
    if "db_conn" not in g:
        g.db_conn = connect()
    return g.db_conn


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection | None = None) -> Iterator[sqlite3.Connection]:
    """Run a block atomically, rolling back on any exception.

    Stock deduction and allocation must not half-apply, which the previous
    fire-and-forget `conn.commit()` calls could not guarantee.
    """
    conn = conn or get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def query_all(sql: str, params: Sequence[Any] = (), conn: sqlite3.Connection | None = None) -> list[sqlite3.Row]:
    return (conn or get_db()).execute(sql, params).fetchall()


def query_one(sql: str, params: Sequence[Any] = (), conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
    return (conn or get_db()).execute(sql, params).fetchone()


def rows_to_dicts(rows: Sequence[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def table_exists(name: str, conn: sqlite3.Connection | None = None) -> bool:
    row = query_one(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
        (name,),
        conn,
    )
    return row is not None


def has_core_tables(conn: sqlite3.Connection | None = None) -> bool:
    conn = conn or get_db()
    return all(table_exists(t, conn) for t in ("Providers", "Resources", "Requests", "StockLevels"))
