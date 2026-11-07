"""Production configuration guardrails."""

from __future__ import annotations

import pytest

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
