"""MySQL connection management.

One connection per request, stored on Flask's `g` and closed on teardown.
Writes run inside an explicit `transaction()` context manager.

Two things changed when this moved off SQLite, and both matter.

**Where the settings come from.** `connect()` used to resolve its target from
`get_settings()` -- an `lru_cache`d *global*. `create_app` wrote the injected
`Settings` into `app.config["SETTINGS"]`, and the data layer never read it. So
a test that carefully built an isolated temporary database was ignored, every
query went to the developer's real one, and the suite mutated real data as it
ran. It passed anyway, which is the worst part. `_active_settings()` below
reads the settings of the app actually handling the request, and falls back to
the global only outside an app context. See docs/AUDIT.md,
"Broken test isolation".

**What a transaction can still undo.** SQLite's `BEGIN IMMEDIATE` took a
database-wide write lock, so only one writer ever existed and the old
read-then-write allocation code was safe by accident. InnoDB has row-level
locking and many concurrent writers, so that safety is gone -- which is why
the allocation decision now lives in `sp_allocate_request` behind ordered
`SELECT ... FOR UPDATE`. Note that a stored procedure COMMITs internally, so
wrapping a `CALL` in `transaction()` does not make it undoable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pymysql
from flask import current_app, g, has_app_context
from pymysql.constants import FIELD_TYPE
from pymysql.converters import conversions
from pymysql.cursors import DictCursor

from ..core.config import DatabaseSettings, Settings, get_settings

log = logging.getLogger(__name__)

# MySQL returns DECIMAL as Python's decimal.Decimal, which is exact and will
# NOT silently mix with float: `Decimal("3") * 0.5` raises TypeError. That is
# the right default for money-like values, but it would mean touching every
# arithmetic expression in the analytics and AI modules -- which this port is
# explicitly not allowed to change.
#
# So the conversion happens once, here, at the driver boundary. The database
# keeps DECIMAL, where exactness actually matters: all stock arithmetic is
# done in SQL by the triggers and sp_allocate_request. Python only reads
# values to report them, and the JSON API has always serialised them as
# numbers anyway.
_CONVERSIONS = conversions.copy()
_CONVERSIONS[FIELD_TYPE.DECIMAL] = float
_CONVERSIONS[FIELD_TYPE.NEWDECIMAL] = float


def _active_settings() -> Settings:
    """Settings of the app serving this request, not a cached global."""
    if has_app_context():
        settings = current_app.config.get("SETTINGS")
        if settings is not None:
            return settings
    return get_settings()


def connect(database: DatabaseSettings | None = None) -> pymysql.connections.Connection:
    """Open a connection. Callers outside a request context use this directly."""
    cfg = database or _active_settings().database
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        conv=_CONVERSIONS,
        # Explicit transactions only. Autocommit would let a half-finished
        # multi-statement write stand.
        autocommit=False,
        # Fail fast rather than hanging a request on an unreachable server.
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )


def get_db() -> pymysql.connections.Connection:
    """The current request's connection, opening one on first use."""
    if "db_conn" not in g:
        g.db_conn = connect()
    return g.db_conn


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - teardown must never raise
            log.warning("Failed to close the database connection.", exc_info=True)


@contextmanager
def transaction(conn: Any = None) -> Iterator[Any]:
    """Run a block atomically, rolling back on any exception."""
    conn = conn or get_db()
    try:
        conn.begin()
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def query_all(sql: str, params: Sequence[Any] = (), conn: Any = None) -> list[dict[str, Any]]:
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, tuple(params))
        return list(cur.fetchall())


def query_one(sql: str, params: Sequence[Any] = (), conn: Any = None) -> dict[str, Any] | None:
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.fetchone()


def execute(sql: str, params: Sequence[Any] = (), conn: Any = None) -> int:
    """Run a write and return the number of rows it affected."""
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, tuple(params))
        return cur.rowcount


def execute_returning_id(sql: str, params: Sequence[Any] = (), conn: Any = None) -> int:
    with (conn or get_db()).cursor() as cur:
        cur.execute(sql, tuple(params))
        return int(cur.lastrowid)


def call_proc(name: str, params: Sequence[Any], out_vars: Sequence[str],
              conn: Any = None) -> dict[str, Any]:
    """CALL a stored procedure and read back its OUT parameters.

    PyMySQL cannot bind OUT parameters directly, so the documented pattern is
    to pass session variables and SELECT them afterwards -- on the same
    connection, since session variables are per-connection.

    The procedure manages its own transaction and COMMITs before returning,
    so the caller cannot roll a successful CALL back.
    """
    conn = conn or get_db()
    placeholders = ", ".join(["%s"] * len(params) + list(out_vars))
    with conn.cursor() as cur:
        cur.execute(f"CALL {name}({placeholders})", tuple(params))
        # A procedure whose body ends in a SELECT leaves result sets queued;
        # draining them keeps the connection usable for the next statement.
        while cur.nextset():
            pass
        if not out_vars:
            return {}
        cur.execute("SELECT " + ", ".join(f"{v} AS `{v.lstrip('@')}`" for v in out_vars))
        return cur.fetchone() or {}


def rows_to_dicts(rows: Sequence[Any]) -> list[dict[str, Any]]:
    """Kept for call sites written against the sqlite3.Row API.

    DictCursor already yields dicts, so this is now the identity function on
    a list. Left in place so the port is a change of driver, not a rename
    across forty call sites.
    """
    return [dict(row) for row in rows]


def table_exists(name: str, conn: Any = None) -> bool:
    row = query_one(
        """SELECT 1 AS present FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            UNION ALL
           SELECT 1 FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
           LIMIT 1""",
        (name, name), conn,
    )
    return row is not None


def has_core_tables(conn: Any = None) -> bool:
    conn = conn or get_db()
    return all(table_exists(t, conn) for t in ("Providers", "Resources", "Requests", "StockLevels"))
