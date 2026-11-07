"""Database bootstrap, run once at application start."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.config import get_settings
from . import seed

log = logging.getLogger(__name__)


def ensure_database(database_path: Path | str | None = None) -> None:
    """Create the database if missing, otherwise apply schema + seed top-ups.

    Called from the app factory rather than lazily inside request handlers, so a
    misconfigured database fails at boot instead of on a user's first search.
    """
    path = Path(database_path or get_settings().database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        log.info("Database found at %s — applying migrations.", path)
        seed.migrate(path)
    else:
        log.info("No database at %s — creating and seeding.", path)
        seed.main(path)
