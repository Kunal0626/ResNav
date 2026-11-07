"""Small coercion helpers so route handlers stay free of try/except noise.

Every helper raises `ValidationError`, which the error handler renders as a 422
with the offending field name — the previous code silently coerced bad input to
zero, which produced confidently wrong results.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .errors import ValidationError

# India's bounding box is not enforced; these are the global legal ranges.
LAT_RANGE = (-90.0, 90.0)
LON_RANGE = (-180.0, 180.0)


def require_str(data: dict, field: str, *, max_length: int = 500, min_length: int = 1) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"'{field}' is required and must be a non-empty string.", details={"field": field})
    value = value.strip()
    if len(value) < min_length:
        raise ValidationError(f"'{field}' must be at least {min_length} characters.", details={"field": field})
    if len(value) > max_length:
        raise ValidationError(f"'{field}' must be at most {max_length} characters.", details={"field": field})
    return value


def optional_float(data: dict, field: str, default: float | None = None,
                   *, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if data.get(field) in (None, ""):
        return default
    try:
        value = float(data[field])
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be a number.", details={"field": field}) from None
    return _check_bounds(field, value, minimum, maximum)


def optional_int(data: dict, field: str, default: int | None = None,
                 *, minimum: int | None = None, maximum: int | None = None) -> int | None:
    if data.get(field) in (None, ""):
        return default
    try:
        value = int(float(data[field]))
    except (TypeError, ValueError):
        raise ValidationError(f"'{field}' must be an integer.", details={"field": field}) from None
    return int(_check_bounds(field, value, minimum, maximum))


def _check_bounds(field: str, value: float, minimum: float | None, maximum: float | None) -> float:
    if minimum is not None and value < minimum:
        raise ValidationError(f"'{field}' must be at least {minimum}.", details={"field": field})
    if maximum is not None and value > maximum:
        raise ValidationError(f"'{field}' must be at most {maximum}.", details={"field": field})
    return value


def coordinates(data: dict, *, default: tuple[float, float] | None = None) -> tuple[float, float]:
    """Read a lat/lon pair. Returns `default` when both are absent or 0/0.

    0/0 is in the Gulf of Guinea — no relief centre is there, so browsers that
    fail geolocation and post zeros get the default instead of nonsense ranking.
    """
    lat = optional_float(data, "latitude", None, minimum=LAT_RANGE[0], maximum=LAT_RANGE[1])
    lon = optional_float(data, "longitude", None, minimum=LON_RANGE[0], maximum=LON_RANGE[1])
    if lat is None or lon is None or (lat == 0 and lon == 0):
        if default is None:
            raise ValidationError("'latitude' and 'longitude' are required.")
        return default
    return lat, lon


def one_of(data: dict, field: str, allowed: Iterable[str], default: str | None = None) -> str:
    allowed = list(allowed)
    value = data.get(field, default)
    if value is None:
        raise ValidationError(f"'{field}' is required.", details={"field": field, "allowed": allowed})
    value = str(value).strip().lower()
    if value not in allowed:
        raise ValidationError(
            f"'{field}' must be one of: {', '.join(allowed)}.",
            details={"field": field, "allowed": allowed},
        )
    return value


def json_body() -> dict[str, Any]:
    """Parsed JSON body, or a 422 rather than a 400 HTML page on malformed input."""
    from flask import request

    if not request.is_json:
        raise ValidationError("Request body must be JSON with Content-Type: application/json.")
    try:
        body = request.get_json(silent=False)
    except Exception:
        raise ValidationError("Request body is not valid JSON.") from None
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    return body
