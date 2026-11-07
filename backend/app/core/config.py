"""Application configuration, loaded from the environment.

One dataclass per deployment target. `get_settings()` picks the right one from
APP_ENV and caches it, so importing this module never touches the environment
more than once.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class ConfigError(RuntimeError):
    """Raised when the environment is missing something required for production."""


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    debug: bool = True
    testing: bool = False

    secret_key: str = "dev-only-insecure-secret"
    database_path: Path = BASE_DIR / "instance" / "resource_navigator.db"

    # Ranking / search tuning.
    geo_scale_km: float = 10.0
    max_results: int = 15

    # Optional integrations.
    google_maps_api_key: str = ""

    # Semantic search. Transformers give better ranking but pull in torch, so
    # the TF-IDF fallback is the default and the heavy path is opt-in.
    enable_transformers: bool = False

    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = "INFO"
    rate_limit_per_minute: int = 120

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def _build() -> Settings:
    env = os.environ.get("APP_ENV", "development").strip().lower()
    is_prod = env == "production"

    secret_key = os.environ.get("SECRET_KEY", "")
    if is_prod and not secret_key:
        raise ConfigError(
            "SECRET_KEY must be set when APP_ENV=production. "
            "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
        )

    db_path = os.environ.get("DATABASE_PATH")
    default_origins = "" if is_prod else "http://localhost:5173,http://127.0.0.1:5173"
    origins = _env_list("CORS_ORIGINS", default_origins)
    if is_prod and not origins:
        raise ConfigError(
            "CORS_ORIGINS must list the frontend origin(s) when APP_ENV=production, "
            "e.g. CORS_ORIGINS=https://resnav.vercel.app"
        )

    return Settings(
        env=env,
        debug=_env_bool("DEBUG", not is_prod),
        testing=_env_bool("TESTING", False),
        secret_key=secret_key or "dev-only-insecure-secret",
        database_path=Path(db_path) if db_path else BASE_DIR / "instance" / "resource_navigator.db",
        geo_scale_km=float(os.environ.get("GEO_SCALE_KM", "10.0")),
        max_results=int(os.environ.get("MAX_RESULTS", "15")),
        google_maps_api_key=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        enable_transformers=_env_bool("ENABLE_TRANSFORMERS", False),
        cors_origins=origins,
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        rate_limit_per_minute=int(os.environ.get("RATE_LIMIT_PER_MINUTE", "120")),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build()


def reset_settings_cache() -> None:
    """Test hook — forces the next `get_settings()` to re-read the environment."""
    get_settings.cache_clear()
