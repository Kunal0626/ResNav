"""Database package: connection handling, queries, schema bootstrap."""

from .bootstrap import ensure_database
from .connection import close_db, connect, get_db, has_core_tables, transaction

__all__ = ["ensure_database", "close_db", "connect", "get_db", "has_core_tables", "transaction"]
