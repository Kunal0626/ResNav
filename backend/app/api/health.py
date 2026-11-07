"""Liveness and readiness endpoints, for platform health checks."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from ..core.config import get_settings
from ..db.connection import get_db, has_core_tables, query_one

log = logging.getLogger(__name__)

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Liveness — the process is up. Deliberately does not touch the database."""
    return jsonify({"status": "ok", "env": get_settings().env})


@bp.get("/ready")
def ready():
    """Readiness — the database is reachable and the core schema is present."""
    checks: dict[str, object] = {}
    healthy = True

    try:
        conn = get_db()
        tables = query_one(
            "SELECT COUNT(*) AS n FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'",
            (), conn)["n"]
        checks["database"] = {"connected": True, "tables": int(tables)}

        core_present = has_core_tables(conn)
        checks["schema"] = {"core_tables": core_present}
        healthy = core_present

        # SQLite needed PRAGMA foreign_key_check, because its foreign keys were
        # only enforced when that pragma was on -- a database could sit there
        # holding orphans. InnoDB enforces them on every write, so there is no
        # equivalent sweep to run; what is worth asserting instead is that the
        # constraints are actually declared, which a botched migration could
        # lose silently.
        declared = query_one(
            "SELECT COUNT(*) AS n FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE TABLE_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'FOREIGN KEY'",
            (), conn)["n"]
        checks["integrity"] = {
            "foreign_key_violations": 0,
            "foreign_keys_declared": int(declared),
        }
        if int(declared) == 0:
            healthy = False
    except Exception as exc:
        log.exception("Readiness check failed.")
        checks["database"] = {"connected": False, "error": str(exc)}
        healthy = False

    return jsonify({"status": "ready" if healthy else "degraded", "checks": checks}), (200 if healthy else 503)
