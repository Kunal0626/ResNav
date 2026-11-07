"""Overview screen: KPIs, provider map, activity feed, risk heatmap.

Notes on what changed from the original `index()` view:

* KPI "AI reasoning" strings used to quote invented figures ("94% within 24h
  SLA", "average latency 4.2 hours") that were never computed from anything.
  They are now derived from the data or omitted.
* Sparklines were `random.uniform` noise seeded at 42. Only the stock series has
  real history behind it, so that is the only series returned; the UI hides the
  rest rather than drawing a fabricated trend.
* The demo-data fallback silently swapped in fictional relief centres that were
  indistinguishable from real ones. It is still there — an empty dashboard is a
  bad first run — but it is flagged with `demo_mode` so the UI can label it.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..db import queries
from ..db.connection import has_core_tables
from ..services import analytics

bp = Blueprint("overview", __name__)

SPARKLINE_POINTS = 7

# Shown only when the database has no providers at all, and always labelled.
DEMO_PROVIDERS = [
    {"id": -1, "name": "Northern Relief Command", "latitude": 28.6139, "longitude": 77.2090,
     "city": "Delhi", "resource_types": "Water, Food, Medicine", "total_stock": 1450},
    {"id": -2, "name": "Coastal Logistics Hub", "latitude": 13.0827, "longitude": 80.2707,
     "city": "Chennai", "resource_types": "Rescue Kits, Boats", "total_stock": 890},
    {"id": -3, "name": "Central Medical Reserve", "latitude": 18.9388, "longitude": 72.8354,
     "city": "Mumbai", "resource_types": "Vitamins, Vaccines", "total_stock": 2100},
]

DEMO_STATS = {
    "total_providers": 3, "total_stock": 4440, "active_requests": 0,
    "pending_allocations": 0, "low_stock_alerts": 0,
}


def _stock_sparkline() -> list[float] | None:
    """Last N days of total stock on hand, or None when history is too thin."""
    daily = queries.stock_history_daily_totals()
    if len(daily) < 2:
        return None
    return [round(float(row["total"] or 0), 1) for row in daily[-SPARKLINE_POINTS:]]


def _kpi_context(stats: dict, providers: list[dict]) -> dict[str, str]:
    """One factual sentence per KPI. Every number here comes from a query."""
    cities = {p.get("city") for p in providers if p.get("city")}
    context = {
        "providers": (
            f"{stats.get('total_providers', 0)} relief centres across "
            f"{len(cities)} cities."
        ),
        "stock": f"{stats.get('total_stock', 0):,.0f} units on hand across all centres.",
        "requests": f"{stats.get('active_requests', 0)} requests not yet fulfilled.",
        "pending": f"{stats.get('pending_allocations', 0)} requests awaiting a first allocation.",
    }

    low = stats.get("low_stock_alerts", 0)
    context["low_stock"] = (
        f"{low} stock lines are below their configured safety threshold."
        if low else "All stock lines are above their safety thresholds."
    )
    return context


@bp.get("/overview")
def overview():
    if not has_core_tables():
        return jsonify({
            "demo_mode": True,
            "providers": DEMO_PROVIDERS,
            "stats": DEMO_STATS,
            "recent_allocations": [],
            "recent_requests": [],
            "insights": ["Database not initialised — showing sample data."],
            "heatmap": [],
            "sparklines": {},
            "kpi_context": _kpi_context(DEMO_STATS, DEMO_PROVIDERS),
            "ticker": ["Sample data — connect a seeded database to see live figures."],
            "status": {"level": "nominal", "fulfilment_rate": 0, "unmet_demand": 0},
        })

    providers = queries.providers_with_stock()
    stats = queries.overview_stats()

    if not providers:
        return jsonify({
            "demo_mode": True,
            "providers": DEMO_PROVIDERS,
            "stats": DEMO_STATS,
            "recent_allocations": [],
            "recent_requests": [],
            "insights": ["No providers are registered yet — showing sample data."],
            "heatmap": [],
            "sparklines": {},
            "kpi_context": _kpi_context(DEMO_STATS, DEMO_PROVIDERS),
            "ticker": ["Sample data — seed the database to see live figures."],
            "status": {"level": "nominal", "fulfilment_rate": 0, "unmet_demand": 0},
        })

    sparkline = _stock_sparkline()

    return jsonify({
        "demo_mode": False,
        "providers": providers,
        "stats": stats,
        "recent_allocations": queries.recent_allocations(5),
        "recent_requests": queries.recent_requests(5),
        "insights": analytics.generate_insights(),
        "heatmap": analytics.city_risk_heatmap(),
        "sparklines": {"stock": sparkline} if sparkline else {},
        "kpi_context": _kpi_context(stats, providers),
        "ticker": analytics.ticker_messages(),
        "status": analytics.system_status(),
    })


@bp.get("/reference")
def reference():
    """Resources, zones and emergency contacts — the dropdown/lookup data."""
    return jsonify({
        "resources": queries.list_resources(),
        "zones": queries.list_zones(),
        "emergency_contacts": queries.list_emergency_contacts(),
    })
