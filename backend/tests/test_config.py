"""Production configuration guardrails."""

from __future__ import annotations

import pytest

from app import create_app
from app.core.config import ConfigError, _build, reset_settings_cache


@pytest.fixture(autouse=True)
def clear_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_production_requires_a_secret_key(monkeypatch):
    """The original shipped a hardcoded default secret and used it in prod."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://resnav.example")

    with pytest.raises(ConfigError, match="SECRET_KEY"):
        _build()


def test_production_requires_explicit_cors_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(ConfigError, match="CORS_ORIGINS"):
        _build()


def test_production_disables_debug_by_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("CORS_ORIGINS", "https://resnav.example")

    settings = _build()
    assert settings.debug is False
    assert settings.is_production is True


def test_development_defaults_are_usable_without_env(monkeypatch):
    for name in ("APP_ENV", "SECRET_KEY", "CORS_ORIGINS", "DEBUG"):
        monkeypatch.delenv(name, raising=False)

    settings = _build()
    assert settings.env == "development"
    assert "http://localhost:5173" in settings.cors_origins


def test_transformers_are_opt_in(monkeypatch):
    monkeypatch.delenv("ENABLE_TRANSFORMERS", raising=False)
    assert _build().enable_transformers is False


def test_connection_uses_the_app_settings_not_a_cached_global(app, settings):
    """Regression test for the defect in docs/AUDIT.md.

    `connect()` used to resolve its target from the lru_cached global
    `get_settings()`, so the Settings injected into `create_app` were written
    to app.config and then ignored by the data layer. Every test silently ran
    against the developer's real database.

    This asserts the fix directly: inside an app context, the connection layer
    must report the app's own target, even when the global disagrees.
    """
    import os

    from app.core.config import DatabaseSettings, Settings
    from app.db.connection import _active_settings

    sentinel = Settings(
        env="testing",
        testing=True,
        secret_key="sentinel",
        database=DatabaseSettings(
            host="203.0.113.1", port=3307,
            user="nobody", password="", database="a_database_that_does_not_exist",
        ),
    )
    other = create_app(sentinel)

    with other.app_context():
        resolved = _active_settings().database
        assert resolved.database == "a_database_that_does_not_exist"
        assert resolved.host == "203.0.113.1"

    # And the real app still resolves to the real target, so the lookup is
    # genuinely per-app rather than per-process.
    with app.app_context():
        assert _active_settings().database.database == settings.database.database

    # Outside any app context it falls back to the environment, as documented.
    assert _active_settings().database.database == os.environ.get("DRA_MYSQL_DB", "resnav")


def test_the_suite_does_not_depend_on_run_order(client, reference):
    """The seed is reloaded before every test, so the data each test sees is
    identical no matter what ran before it. The old suite could not say this:
    it drained shared stock until the third consecutive run failed."""
    stock = client.get("/api/stock").get_json()["stock"]
    total = sum(row["quantity"] for row in stock)
    assert total == 2505, (
        "the seeded total changed, which means a previous test's writes "
        "survived into this one"
    )
