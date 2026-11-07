"""Derived metrics for the overview and command-centre screens.

Replaces `ai_engine.generate_insights`, which queried the legacy compatibility
views (`Location`, `ServiceProvider.location_id`) that no longer carry those
columns. Every one of its queries raised, and a bare `except: pass` meant the
insights panel silently rendered empty instead of reporting the failure.
"""

from __future__ import annotations

import logging
from typing import Any

from ..db import queries

log = logging.getLogger(__name__)

# A city holding less than this across all resources is flagged as at-risk.
LOW_CITY_STOCK = 100.0

# Share of allocations concentrated in the top providers before we call it out.
CONCENTRATION_THRESHOLD = 0.5


def generate_insights() -> list[str]:
    """Plain-language observations drawn from current data. Never fabricated."""
    insights: list[str] = []

    performance = queries.provider_performance()
    total_allocations = sum(p["total"] for p in performance)
    if total_allocations > 0:
        top = sorted(performance, key=lambda p: p["total"], reverse=True)[:2]
        share = sum(p["total"] for p in top) / total_allocations
        if share >= CONCENTRATION_THRESHOLD:
            names = " and ".join(p["provider"] for p in top)
            insights.append(
                f"{names} are handling {share:.0%} of all allocations — "
                f"concentration risk if either goes offline."
            )

    low_stock = queries.stock_levels(low_only=True)
    if low_stock:
        worst = min(low_stock, key=lambda s: s["quantity"] / max(s["threshold"], 1))
        insights.append(
            f"{len(low_stock)} stock lines are below their safety threshold; "
            f"{worst['resource_name']} at {worst['provider_name']} is the most depleted "
            f"({worst['quantity']:.0f} of {worst['threshold']:.0f})."
        )

    zones = queries.zone_metrics()
    starved = [
        z for z in zones
        if z["total_demand"] > 0 and z["total_supplied"] < z["total_demand"] * 0.5
    ]
    if starved:
        worst_zone = max(starved, key=lambda z: z["total_demand"] - z["total_supplied"])
        gap = worst_zone["total_demand"] - worst_zone["total_supplied"]
        insights.append(
            f"{worst_zone['zone_name']} has an unmet demand gap of {gap:.0f} units "
            f"across {worst_zone['total_requests']} requests."
        )

    pending = [z for z in zones if z["pending_requests"] > 0]
    if pending:
        total_pending = sum(z["pending_requests"] for z in pending)
        insights.append(
            f"{total_pending} requests are still pending dispatch across "
            f"{len(pending)} zones."
        )

    if not insights:
        insights.append("All monitored indicators are within normal thresholds.")
    return insights


def city_risk_heatmap() -> list[dict[str, Any]]:
    """Per-city risk intensity in [0, 1] for the map overlay.

    Risk rises with unmet demand and falls with stock on hand, so a city with
    both high demand and deep reserves reads as lower risk than demand alone
    would suggest.
    """
    providers = queries.providers_with_stock()
    if not providers:
        return []

    by_city: dict[str, dict[str, Any]] = {}
    for provider in providers:
        city = provider.get("city") or "Unknown"
        entry = by_city.setdefault(city, {
            "city": city,
            "lat": provider["latitude"],
            "lon": provider["longitude"],
            "stock": 0.0,
            "providers": 0,
        })
        entry["stock"] += float(provider["total_stock"] or 0.0)
        entry["providers"] += 1

    max_stock = max((c["stock"] for c in by_city.values()), default=0.0)
    if max_stock <= 0:
        # No stock anywhere: every city is equally and maximally at risk.
        return [{**c, "risk_intensity": 1.0} for c in by_city.values()]

    results = []
    for city in by_city.values():
        # Inverted stock share: the emptier a city, the hotter it reads.
        intensity = 1.0 - (city["stock"] / max_stock)
        results.append({
            "city": city["city"],
            "lat": city["lat"],
            "lon": city["lon"],
            "stock": round(city["stock"], 1),
            "providers": city["providers"],
            "risk_intensity": round(max(0.05, min(1.0, intensity)), 3),
        })
    return sorted(results, key=lambda c: c["risk_intensity"], reverse=True)


def system_status() -> dict[str, Any]:
    """Operational summary used by the header status pill and the ticker."""
    stats = queries.overview_stats()
    zones = queries.zone_metrics()

    demand = sum(z["total_demand"] for z in zones)
    supplied = sum(z["total_supplied"] for z in zones)
    fulfilment = round((supplied / demand) * 100, 1) if demand else 100.0

    if stats.get("low_stock_alerts", 0) > 0 or fulfilment < 60:
        level = "degraded"
    elif stats.get("pending_allocations", 0) > 0:
        level = "busy"
    else:
        level = "nominal"

    return {
        "level": level,
        "fulfilment_rate": fulfilment,
        "unmet_demand": round(max(0.0, demand - supplied), 1),
        **stats,
    }


def ticker_messages() -> list[str]:
    """Short status lines for the scrolling ticker, derived from live counters."""
    stats = queries.overview_stats()
    messages: list[str] = []

    if stats.get("low_stock_alerts", 0) > 0:
        messages.append(
            f"Stock alert — {stats['low_stock_alerts']} lines below safety threshold.")
    if stats.get("pending_allocations", 0) > 0:
        messages.append(
            f"Dispatch queue — {stats['pending_allocations']} allocations awaiting action.")
    if stats.get("active_requests", 0) > 0:
        messages.append(f"{stats['active_requests']} requests currently active across all zones.")

    status = system_status()
    messages.append(f"Fulfilment rate at {status['fulfilment_rate']}% of total requested volume.")
    messages.append(
        f"{stats.get('total_providers', 0)} relief centres online holding "
        f"{stats.get('total_stock', 0):,} units."
    )
    return messages
