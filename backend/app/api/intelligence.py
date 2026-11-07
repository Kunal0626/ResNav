"""AI command centre and forecasting endpoints.

These assemble database rows into the shapes the `app.ai` modules expect, then
return their output. The mapping functions live here so the AI modules stay pure
and testable without a database.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify

from .. import ai
from ..db import queries
from ..db.connection import has_core_tables

log = logging.getLogger(__name__)

bp = Blueprint("intelligence", __name__)

# Depletion horizons, in days, that map to the UI's status colours.
CRITICAL_DAYS, WARNING_DAYS = 7, 21

# A resource with no recorded consumption is reported as stable rather than
# being assigned an arbitrary large "days remaining" number.
STABLE = "Stable"

# Shortest window a burn rate may be averaged over. Movements clustered in a few
# seconds do not evidence a per-second consumption rate.
MIN_OBSERVATION_DAYS = 1.0


def _zone_inputs() -> list[dict[str, Any]]:
    """Zone rows shaped for the risk predictor.

    `stock_shortage_ratio` is computed from real demand versus supply. The
    original hardcoded 0.5 for every zone, which pinned the model's most heavily
    weighted feature to a constant and made all zone risks near-identical.
    """
    zones = []
    for row in queries.zone_metrics():
        demand = float(row["total_demand"] or 0)
        supplied = float(row["total_supplied"] or 0)
        shortage = (demand - supplied) / demand if demand > 0 else 0.0
        zones.append({
            "zone_name": row["zone_name"],
            "total_requests": int(row["total_requests"] or 0),
            "pending_requests": int(row["pending_requests"] or 0),
            "avg_severity": round(float(row["avg_severity"] or 1.0), 2),
            "avg_urgency": round(float(row["avg_urgency"] or 1.0), 2),
            "population_affected": int(row["population_affected"] or 0),
            "disaster_category": (row.get("risk_level") or "unknown").lower(),
            "stock_shortage_ratio": round(max(0.0, min(1.0, shortage)), 3),
            "recent_request_trend": 0.0,
        })
    return zones


def _anomaly_inputs() -> dict[str, Any]:
    performance = queries.provider_performance()
    return {
        "provider_performance": [
            {
                "provider": row["provider"],
                "total": row["total"],
                "success_rate": round(row["successful"] / max(1, row["total"]), 2),
            }
            for row in performance
        ],
        "stock_levels": [
            {
                "provider": row["provider_name"],
                "resource": row["resource_name"],
                "current": float(row["quantity"]),
                "previous": float(row["threshold"]),
            }
            for row in queries.stock_levels()
        ],
        "request_volumes": [
            {"resource": row["resource"], "volumes": [row["volume"]]}
            for row in queries.request_volume_by_resource()
        ],
    }


def _stock_levels_for_insights() -> list[dict[str, Any]]:
    return [
        {
            "provider": row["provider_name"],
            "resource": row["resource_name"],
            "resource_type": row["resource_name"],
            "quantity": float(row["quantity"]),
            "threshold": float(row["threshold"]),
        }
        for row in queries.stock_levels()
    ]


@bp.get("/dashboard")
def dashboard():
    """Command centre: forecasts, zone risks, anomalies and generated insights."""
    if not has_core_tables():
        return jsonify({"forecasts": [], "zone_risks": [], "anomalies": [],
                        "insights": [], "available": False})

    history = queries.stock_history(limit=1000)
    forecasts = ai.forecast_depletion(history).get("forecasts", [])[:5] if history else []
    zone_risks = ai.predict_zone_risks(_zone_inputs()).get("zone_risks", [])
    anomalies = ai.detect_anomalies(_anomaly_inputs()).get("anomalies", [])
    insights = ai.generate_insights(
        forecasts=forecasts,
        zone_risks=zone_risks,
        anomalies=anomalies,
        stock_levels=_stock_levels_for_insights(),
    ).get("insights", [])

    return jsonify({
        "available": True,
        "forecasts": forecasts,
        "zone_risks": zone_risks,
        "anomalies": anomalies,
        "insights": insights,
    })


def _depletion_rows(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per (provider, resource) burn rate and days of cover, from stock history."""
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for row in history:
        key = (row["provider_name"], row["resource_name"])
        try:
            when = datetime.strptime(str(row["created_at"]), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            continue
        groups.setdefault(key, []).append({"qty": float(row["quantity_after"] or 0), "at": when})

    results = []
    for (provider, resource), points in groups.items():
        points.sort(key=lambda p: p["at"])
        if len(points) < 2:
            continue

        # Floor the observation window at one day. Several movements recorded
        # within the same minute would otherwise divide by a near-zero span and
        # report burn rates in the tens of thousands per day.
        span_days = max(
            MIN_OBSERVATION_DAYS,
            (points[-1]["at"] - points[0]["at"]).total_seconds() / 86400,
        )
        drawdown = sum(
            max(0.0, points[i - 1]["qty"] - points[i]["qty"])
            for i in range(1, len(points))
        )
        daily_rate = drawdown / span_days
        current = points[-1]["qty"]

        if daily_rate <= 0:
            days_left: float | str = STABLE
            risk_score = 5
        else:
            days_left = round(current / daily_rate, 1)
            # Hyperbolic decay, not linear: 100 at zero cover, 50 at the
            # critical horizon, 25 at the warning horizon, approaching zero
            # asymptotically. A linear ramp reached zero at ~11 days, so lines
            # flagged "Warning" still reported a risk score of 0.
            risk_score = int(round(100 * CRITICAL_DAYS / (CRITICAL_DAYS + days_left)))

        results.append({
            "provider": provider,
            "resource": resource,
            "current_stock": round(current, 1),
            "daily_rate": round(daily_rate, 2),
            "days_left": days_left,
            "risk_score": risk_score,
            "status": (
                "Critical" if isinstance(days_left, float) and days_left < CRITICAL_DAYS
                else "Warning" if isinstance(days_left, float) and days_left < WARNING_DAYS
                else "Low"
            ),
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results


@bp.get("/forecast")
def forecast():
    """Depletion forecast panel: per-line burn rates, risk zones, history chart.

    The original view silently invented 15 days of synthetic stock movements
    whenever real history was thin, and rendered them as if measured. Real data
    only here; `sufficient_history` tells the UI when to show an empty state.
    """
    if not has_core_tables():
        return jsonify({"forecast": [], "risk_zones": [], "history": [],
                        "sufficient_history": False, "available": False})

    history = queries.stock_history(limit=1000)
    rows = _depletion_rows(history)

    numeric_days = [r["days_left"] for r in rows if isinstance(r["days_left"], float)]
    nearest = min(numeric_days) if numeric_days else None
    avg_risk = int(sum(r["risk_score"] for r in rows) / len(rows)) if rows else 0

    # The summary keys off the most urgent line, not the mean. Averaging across
    # many stable lines hid a single line hours from stocking out, so the panel
    # could read "within acceptable thresholds" beside a 0.0-day runway.
    critical = [r for r in rows if r["status"] == "Critical"]
    warning = [r for r in rows if r["status"] == "Warning"]

    if not rows:
        summary = "Not enough stock movement recorded yet to project depletion."
    elif critical:
        worst = min(critical, key=lambda r: r["days_left"])
        summary = (
            f"{len(critical)} resource line(s) will stock out within {CRITICAL_DAYS} days — "
            f"{worst['resource']} at {worst['provider']} has {worst['days_left']} days of cover. "
            f"Redistribute from surplus centres."
        )
    elif warning:
        summary = (
            f"{len(warning)} resource line(s) fall below safe cover within {WARNING_DAYS} days. "
            f"Consider pre-positioning stock."
        )
    else:
        summary = "Stock levels are within acceptable thresholds at current burn rates."

    return jsonify({
        "available": True,
        "sufficient_history": len(rows) > 0,
        "forecast": rows[:20],
        "risk_zones": [
            {"zone": r["provider"], "resource": r["resource"],
             "risk": r["risk_score"], "days": r["days_left"]}
            for r in rows if r["risk_score"] > 50
        ][:10],
        "avg_risk_index": avg_risk,
        # Peak matters more than mean for triage: one line about to stock
        # out is an incident, regardless of how calm the average looks.
        "peak_risk_index": max((r["risk_score"] for r in rows), default=0),
        "critical_lines": len(critical),
        "nearest_depletion": nearest,
        "ai_summary": summary,
        "history": [
            {
                "provider_name": row["provider_name"],
                "resource_name": row["resource_name"],
                "quantity_before": row["quantity_before"],
                "quantity_after": row["quantity_after"],
                "change_type": row["change_type"],
                "created_at": str(row["created_at"] or ""),
            }
            for row in history
        ],
    })


@bp.get("/forecast/series")
def forecast_series():
    """Aggregate daily stock totals plus a projected continuation."""
    daily = queries.stock_history_daily_totals()
    series = [
        {"qty": float(row["total"] or 0), "time": f"{row['day']} 00:00:00"}
        for row in daily if row["day"]
    ]
    return jsonify(ai.generate_time_series_forecast(series))


@bp.get("/explorer")
def explorer():
    """Read-only view over the core tables, with chart-ready aggregates."""
    if not has_core_tables():
        return jsonify({"available": False, "providers": [], "resources": [], "stock": [],
                        "requests": [], "allocations": [], "charts": {}})

    stock_totals = queries.stock_totals_by_resource()
    status_counts = queries.request_counts_by_status()

    return jsonify({
        "available": True,
        "providers": queries.list_providers(),
        "resources": queries.list_resources(),
        "stock": queries.stock_levels(),
        "requests": queries.list_requests(limit=100),
        "allocations": queries.list_allocations(limit=100),
        "charts": {
            "stock_by_resource": {
                "labels": [r["resource"] for r in stock_totals],
                "values": [float(r["quantity"]) for r in stock_totals],
            },
            "requests_by_status": {
                "labels": [str(r["status"]).capitalize() for r in status_counts],
                "values": [r["count"] for r in status_counts],
            },
        },
    })
