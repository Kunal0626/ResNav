"""Liveness and readiness endpoints, for platform health checks."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from ..core.config import get_settings
from ..db.connection import get_db, has_core_tables

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
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
        checks["database"] = {"connected": True, "tables": tables}

        core_present = has_core_tables(conn)
        checks["schema"] = {"core_tables": core_present}
        healthy = core_present

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        checks["integrity"] = {"foreign_key_violations": len(violations)}
        if violations:
            healthy = False
    except Exception as exc:
        log.exception("Readiness check failed.")
        checks["database"] = {"connected": False, "error": str(exc)}
        healthy = False

    return jsonify({"status": "ready" if healthy else "degraded", "checks": checks}), (200 if healthy else 503)
