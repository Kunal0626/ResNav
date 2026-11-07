"""Shared fixtures. Every test runs against its own isolated database.

That sentence was in this file before the port and was **not true**. The
fixtures built an isolated temporary database, but `connection.connect()`
resolved its target from the `lru_cache`d global `get_settings()` rather than
the `Settings` injected into `create_app`, so every request went to the
developer's real database instead. The suite passed, mutated real data as it
ran, and started failing on its third consecutive run as the stock it drew on
was used up. See docs/AUDIT.md, "Broken test isolation".

Two things make it true now:

  1. `connection._active_settings()` reads `current_app.config["SETTINGS"]`
     when there is an app context, so an injected Settings is actually used.
  2. The data is reloaded from db/seed/ before EVERY test, so no test can
     see another's writes and the order they run in cannot matter. That is
     the property the old suite lacked.

By default this uses the development database, because granting an account
rights on a second one is an extra setup step a stranger would have to be
talked through. The seed is deterministic, so the only cost is that the suite
leaves the database at seed-plus-last-test; `./run.sh test` reloads it
afterwards. Set DRA_MYSQL_TEST_DB to use a separate database instead -- the
account then needs `GRANT ALL ON <that database>.*`.

`test_connection_uses_the_app_settings` in test_config.py asserts the first
point directly, so the defect cannot come back unnoticed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.core.config import DatabaseSettings, Settings  # noqa: E402
from app.db.connection import connect  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = REPO_ROOT / "db"


def _target() -> DatabaseSettings:
    """Where the tests write."""
    base = os.environ.get("DRA_MYSQL_DB", "resnav")
    return DatabaseSettings(
        host=os.environ.get("DRA_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("DRA_MYSQL_PORT", "3306")),
        user=os.environ.get("DRA_MYSQL_USER", "resnav_app"),
        password=os.environ.get("DRA_MYSQL_PASSWORD", ""),
        database=os.environ.get("DRA_MYSQL_TEST_DB", base),
    )


def _run_sql_files(cfg: DatabaseSettings, files: list[Path]) -> None:
    conn = connect(cfg)
    try:
        for path in files:
            sql = path.read_text()
            # The schema files use DELIMITER, which is a client instruction
            # rather than SQL, so they are split on it here the way the mysql
            # client would.
            for statement in _split(sql):
                with conn.cursor() as cur:
                    cur.execute(statement)
        conn.commit()
    finally:
        conn.close()


def _split(sql: str) -> list[str]:
    """Split a script into statements, honouring DELIMITER."""
    statements: list[str] = []
    delimiter = ";"
    buffer: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            if buffer:
                statements.append("\n".join(buffer))
                buffer = []
            delimiter = stripped.split(None, 1)[1].strip()
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            joined = "\n".join(buffer).rstrip()
            joined = joined[: -len(delimiter)].strip()
            # Strip leading comment and blank lines. Without this a statement
            # preceded by a comment is judged to BE a comment and silently
            # dropped -- which quietly skipped the first DROP TABLE in the
            # schema and produced a baffling "cannot drop, referenced by a
            # foreign key" twelve statements later.
            lines = joined.splitlines()
            while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
                lines.pop(0)
            joined = "\n".join(lines).strip()
            if joined:
                statements.append(joined)
            buffer = []
    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if s.strip()]


@pytest.fixture(scope="session")
def database() -> DatabaseSettings:
    """Build the test database once: schema, routines, triggers, views."""
    cfg = _target()

    if cfg.database != os.environ.get("DRA_MYSQL_DB", "resnav"):
        # Only when pointed at a dedicated test database, which needs its own
        # grant. Against the development database there is nothing to create.
        admin = connect(DatabaseSettings(cfg.host, cfg.port, cfg.user, cfg.password,
                                         os.environ.get("DRA_MYSQL_DB", "resnav")))
        try:
            with admin.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{cfg.database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
            admin.commit()
        finally:
            admin.close()

    files = sorted(DB_DIR.glob("schema/*.sql")) + sorted(DB_DIR.glob("procedures/*.sql")) \
        + sorted(DB_DIR.glob("triggers/*.sql")) + sorted(DB_DIR.glob("views/*.sql"))
    _run_sql_files(cfg, files)
    return cfg


@pytest.fixture
def settings(database: DatabaseSettings) -> Settings:
    """Reload the data before every test, so order cannot matter."""
    _run_sql_files(database, sorted(DB_DIR.glob("seed/*.sql")))
    return Settings(
        env="testing",
        testing=True,
        debug=False,
        secret_key="test-secret",
        database=database,
        cors_origins=["http://localhost:5173"],
        log_level="WARNING",
    )


@pytest.fixture
def app(settings):
    application = create_app(settings)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def reference(client):
    return client.get("/api/reference").get_json()
