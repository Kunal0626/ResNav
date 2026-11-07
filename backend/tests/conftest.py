"""Shared fixtures. Every test runs against a fresh, seeded temporary database."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.bootstrap import ensure_database  # noqa: E402


@pytest.fixture(scope="session")
def seeded_database(tmp_path_factory) -> Path:
    """Seed one database per test session — schema creation is the slow part."""
    path = tmp_path_factory.mktemp("db") / "test.db"
    ensure_database(path)
    return path


@pytest.fixture
def settings(seeded_database, tmp_path) -> Settings:
    # Copy the seeded database so mutating tests cannot affect one another.
    import shutil

    working = tmp_path / "resnav.db"
    shutil.copy(seeded_database, working)
    return Settings(
        env="testing",
        testing=True,
        debug=False,
        secret_key="test-secret",
        database_path=working,
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
