#!/usr/bin/env python3
"""Developer CLI: run the dev server, seed the database, inspect health."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from app import create_app
from app.core.config import get_settings
from app.db.bootstrap import ensure_database

log = logging.getLogger("manage")


def cmd_seed(_args: argparse.Namespace) -> int:
    settings = get_settings()
    ensure_database(settings.database_path)
    print(f"Database ready at {settings.database_path}")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """Verify the database is reachable and structurally sound."""
    app = create_app()
    with app.test_client() as client:
        response = client.get("/api/ready")
        payload = response.get_json()

    print(f"status: {payload.get('status')}")
    for name, detail in (payload.get("checks") or {}).items():
        print(f"  {name}: {detail}")
    return 0 if response.status_code == 200 else 1


def cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to start the development server with APP_ENV=production.",
              file=sys.stderr)
        print("Use: gunicorn --config gunicorn.conf.py wsgi:app", file=sys.stderr)
        return 1

    app = create_app()
    app.run(host=args.host, port=args.port, debug=settings.debug, use_reloader=args.reload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ResNav backend management commands.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Start the development server.")
    # Binds to localhost by default. The original hardcoded 0.0.0.0 with
    # debug=True, exposing a Werkzeug debugger console to the whole network.
    run.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    run.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5001)))
    run.add_argument("--reload", action="store_true", help="Enable the auto-reloader.")
    run.set_defaults(func=cmd_run)

    sub.add_parser("seed", help="Create or migrate the database.").set_defaults(func=cmd_seed)
    sub.add_parser("check", help="Run readiness diagnostics.").set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
