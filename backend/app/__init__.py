"""Application factory.

The original `app.py` created a module-level `Flask()` at import time, which
made configuration global, tests unable to vary settings, and every route file
implicitly dependent on import order. A factory fixes all three.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from .core.config import Settings, get_settings
from .core.errors import register_error_handlers
from .core.logging import configure_logging

log = logging.getLogger(__name__)

API_PREFIX = "/api"

# Bodies larger than this are rejected before a handler ever sees them.
MAX_BODY_BYTES = 1 * 1024 * 1024


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.is_production)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
        SETTINGS=settings,
    )

    _register_cors(app, settings)
    _register_security_headers(app)
    _register_blueprints(app)
    register_error_handlers(app)

    from .db.connection import close_db

    app.teardown_appcontext(close_db)

    if not settings.testing:
        from .db.bootstrap import ensure_database

        ensure_database(settings.database_path)

    @app.get("/")
    def root():
        return jsonify({
            "service": "resnav-api",
            "env": settings.env,
            "health": f"{API_PREFIX}/health",
        })

    log.info("ResNav API ready (env=%s, transformers=%s).",
             settings.env, settings.enable_transformers)
    return app


def _register_blueprints(app: Flask) -> None:
    from .api import ai_modules, health, intelligence, inventory, overview, search

    app.register_blueprint(health.bp, url_prefix=API_PREFIX)
    app.register_blueprint(overview.bp, url_prefix=API_PREFIX)
    app.register_blueprint(search.bp, url_prefix=API_PREFIX)
    app.register_blueprint(intelligence.bp, url_prefix=API_PREFIX)
    app.register_blueprint(inventory.bp, url_prefix=API_PREFIX)
    app.register_blueprint(ai_modules.bp, url_prefix=f"{API_PREFIX}/ai")


def _register_cors(app: Flask, settings: Settings) -> None:
    """Allow the configured frontend origins, and nothing else.

    Written directly rather than pulling in flask-cors: the policy is a few
    headers plus an OPTIONS short-circuit, and this keeps the dependency list
    honest about what is actually needed.
    """
    allowed = set(settings.cors_origins)

    @app.before_request
    def _preflight():
        # Answered here rather than via a catch-all OPTIONS route: a
        # `/<path:...>` rule matches every URL, which turns what should be a 404
        # on an unknown path into a 405.
        if request.method == "OPTIONS":
            return "", 204
        return None

    @app.after_request
    def _apply_cors(response):
        origin = request.headers.get("Origin")
        if origin and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "600"
        return response


def _register_security_headers(app: Flask) -> None:
    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
