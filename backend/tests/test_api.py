"""Endpoint contract tests: every route answers, and answers in the right shape."""

from __future__ import annotations

import pytest

GET_ENDPOINTS = [
    "/api/health",
    "/api/ready",
    "/api/overview",
    "/api/reference",
    "/api/dashboard",
    "/api/forecast",
    "/api/forecast/series",
    "/api/explorer",
    "/api/stock",
    "/api/requests",
    "/api/allocations",
    "/api/logs",
    "/api/ai/forecast",
    "/api/ai/risk-predict",
    "/api/ai/anomaly-detect",
    "/api/ai/insights",
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_endpoints_return_json(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.is_json


def test_root_describes_the_service(client):
    body = client.get("/").get_json()
    assert body["service"] == "resnav-api"


def test_unknown_path_is_404_not_405(client):
    """A catch-all OPTIONS route used to turn every unknown path into a 405."""
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_overview_reports_real_counts(client):
    body = client.get("/api/overview").get_json()
    assert body["demo_mode"] is False
    assert body["stats"]["total_providers"] > 0
    assert isinstance(body["insights"], list) and body["insights"]


def test_overview_omits_sparklines_it_cannot_derive(client):
    """Only series with real history are returned; none are fabricated."""
    body = client.get("/api/overview").get_json()
    assert set(body["sparklines"]).issubset({"stock"})


def test_security_headers_present(client):
    headers = client.get("/api/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"


def test_cors_allows_configured_origin_only(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"

    denied = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_error_responses_never_leak_tracebacks(client):
    """The original handler serialised `traceback.format_exc()` to the client."""
    response = client.get("/api/requests/999999/recommendation")
    assert response.status_code == 404
    assert "traceback" not in response.get_data(as_text=True).lower()
