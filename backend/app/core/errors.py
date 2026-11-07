"""Uniform error envelope for the API.

Every failure — expected or not — leaves as
`{"error": {"code": ..., "message": ..., "details": ...}}` with a sane status.
Tracebacks are logged, never serialised to the client.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for errors we raise deliberately and can safely show a user."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return {"error": payload}


class ValidationError(ApiError):
    status_code = 422
    code = "validation_error"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    """Business-rule violation, e.g. allocating more stock than exists."""

    status_code = 409
    code = "conflict"


class ServiceUnavailableError(ApiError):
    status_code = 503
    code = "service_unavailable"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        if exc.status_code >= 500:
            log.exception("API error: %s", exc.message)
        else:
            log.info("API error %s: %s", exc.status_code, exc.message)
        return jsonify(exc.to_dict()), exc.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_error(exc: HTTPException):
        # Preserves 404/405/413 etc. instead of flattening them into 500s.
        return (
            jsonify({"error": {"code": exc.name.lower().replace(" ", "_"), "message": exc.description}}),
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        log.exception("Unhandled exception: %s", exc)
        return (
            jsonify({"error": {"code": "internal_error", "message": "An unexpected server error occurred."}}),
            500,
        )
