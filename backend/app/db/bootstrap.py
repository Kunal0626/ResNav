"""Database bootstrap, run once at application start.

On SQLite this created the database file if it was missing. MySQL is a
server: the schema is applied by `make schema`, deliberately outside the
request path, because an application that silently creates its own schema
will happily do so against the wrong database.

So this only VERIFIES, and says plainly what to run if the check fails.
"""

from __future__ import annotations

import logging

from ..core.config import DatabaseSettings
from .connection import connect, has_core_tables

log = logging.getLogger(__name__)


class DatabaseNotReady(RuntimeError):
    """The server is reachable but the schema has not been applied."""


def ensure_database(database: DatabaseSettings | None = None) -> None:
    """Check the server is reachable and the core tables exist."""
    conn = connect(database)
    try:
        if not has_core_tables(conn):
            raise DatabaseNotReady(
                "Connected, but the schema is missing. Apply it with:  ./run.sh schema"
            )
        log.info("Database ready at %s",
                 (database.dsn_for_log() if database else "configured target"))
    finally:
        conn.close()
