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


def test_timestamps_serialise_as_iso_not_http_date(client):
    """Regression test for a port defect that touched every page.

    Under SQLite, timestamps were TEXT columns and reached the browser as
    "YYYY-MM-DD HH:MM:SS". PyMySQL returns real datetime objects, and Flask's
    default JSON provider renders those as an HTTP-date --
    "Sat, 07 Nov 2026 23:08:03 GMT" -- which the frontend's date helpers
    cannot parse, so they printed the raw string instead.

    The "GMT" was the worse half: MySQL's NOW(6) is local wall-clock time
    with no zone, so labelling it GMT shifted every displayed time by the UTC
    offset.

    The offset is now explicit. Omitting it worked only while the browser and
    the database agreed about local time, and they stop agreeing the moment
    this runs in a container -- MySQL is UTC there and IST on the development
    machine, which rendered a just-raised alert as "6 hours ago".
    """
    import re
    from datetime import datetime

    body = client.get("/api/stock").get_json()
    stamp = body["stock"][0]["updated_at"]
    assert "GMT" not in stamp, stamp
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", stamp), stamp
    # And it must be a timestamp a client can actually parse back.
    parsed = datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None


def test_stock_reports_standing_alerts_separately_from_low_lines(client, reference):
    """`is_low` is recomputed per request; an alert is tracked state.

    They are deliberately different numbers and the UI shows both.
    """
    body = client.get("/api/stock").get_json()
    assert "alerts" in body
    for alert in body["alerts"]:
        assert alert["quantity_now"] <= alert["threshold_at_alert"]
        assert alert["raised_at"]

    # Draining a centre must raise one, through the trigger -- not through
    # anything Python does.
    before = len(client.get("/api/stock").get_json()["alerts"])
    created = client.post("/api/requests", json={
        "zone_id": reference["zones"][0]["id"],
        "resource_id": reference["resources"][0]["id"],
        "quantity_requested": 5000,
        "severity": 2.5, "urgency": 2.5, "population_affected": 10000,
    }).get_json()["request"]
    client.post(f"/api/requests/{created['id']}/allocate", json={})
    after = client.get("/api/stock").get_json()["alerts"]
    assert len(after) > before
