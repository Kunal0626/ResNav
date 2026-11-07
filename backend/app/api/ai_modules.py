"""Endpoints for the eight standalone AI modules.

Each route validates input, gathers the context the module needs from the
database, and returns the module's output unchanged.
"""

from __future__ import annotations

import re

from flask import Blueprint, jsonify

from .. import ai
from ..core.validation import json_body, one_of, optional_float, optional_int, require_str
from ..db import queries
from .intelligence import _anomaly_inputs, _stock_levels_for_insights, _zone_inputs
from .search import DEFAULT_LOCATION

bp = Blueprint("ai_modules", __name__)

SCENARIOS = ("flood", "cyclone", "earthquake", "drought", "heatwave")

# Population bounds for the simulation lab — one person up to roughly the
# population of the largest Indian state.
POPULATION_RANGE = (1, 250_000_000)

# Resource categories the simulation engine models.
SIMULATION_CATEGORIES = (
    "water", "food", "medicine", "shelter", "clothing", "sanitation", "rescue_equipment",
)

# Catalogue names map onto those categories by keyword. Without this the naive
# slug of "Water (litres)" was "water_(litres)", which matched nothing — so
# every simulation reported zero stock on hand and a 100% shortage probability
# for every resource, regardless of actual inventory.
SIMULATION_SYNONYMS = {
    "water": "water", "drinking": "water",
    "food": "food", "ration": "food", "grain": "food", "meal": "food",
    "medicine": "medicine", "medical": "medicine", "vaccine": "medicine", "first aid": "medicine",
    "shelter": "shelter", "tent": "shelter", "tarp": "shelter", "bed": "shelter",
    "blanket": "clothing", "cloth": "clothing", "thermal": "clothing",
    "hygiene": "sanitation", "sanitary": "sanitation", "soap": "sanitation", "sanitation": "sanitation",
    "rescue": "rescue_equipment", "boat": "rescue_equipment", "equipment": "rescue_equipment",
}


def _simulation_key(resource_name: str) -> str | None:
    """Map a catalogue resource name onto a simulation category, or None."""
    name = re.sub(r"\(.*?\)", " ", resource_name or "").lower()
    for keyword, category in SIMULATION_SYNONYMS.items():
        if keyword in name:
            return category
    return None


@bp.post("/nlp-understand")
def nlp_understand():
    body = json_body()
    text = require_str(body, "text", max_length=2000)
    return jsonify(ai.understand_request(text))


@bp.post("/recommend-provider")
def recommend_provider():
    body = json_body()
    resource_id = optional_int(body, "resource_id", minimum=1)
    quantity = optional_float(body, "quantity_requested", 1.0, minimum=0.01, maximum=1_000_000)
    urgency = optional_float(body, "urgency", 1.0, minimum=0.1, maximum=3.0)
    lat = optional_float(body, "latitude", DEFAULT_LOCATION[0], minimum=-90, maximum=90)
    lon = optional_float(body, "longitude", DEFAULT_LOCATION[1], minimum=-180, maximum=180)

    if resource_id is None:
        candidates = [
            row for resource in queries.list_resources()
            for row in queries.providers_holding_resource(resource["id"])
        ]
    else:
        candidates = queries.providers_holding_resource(resource_id)

    providers = []
    for row in candidates:
        total = int(row.get("total_allocations") or 0)
        success = int(row.get("successful_allocations") or 0)
        success_rate = round(success / total, 2) if total else 0.7
        providers.append({
            "id": row["id"], "name": row["name"], "city": row.get("city"),
            "latitude": row.get("latitude"), "longitude": row.get("longitude"),
            "stock_level": float(row.get("stock_level") or 0.0),
            "success_rate": success_rate,
            "reliability_score": round(min(1.0, 0.5 + success_rate * 0.5), 2),
        })

    return jsonify(ai.recommend_provider(
        providers=providers, quantity_requested=quantity,
        urgency=urgency, user_lat=lat, user_lon=lon))


@bp.get("/forecast")
def forecast():
    return jsonify(ai.forecast_depletion(queries.stock_history(limit=1000)))


@bp.get("/risk-predict")
def risk_predict():
    return jsonify(ai.predict_zone_risks(_zone_inputs()))


@bp.get("/anomaly-detect")
def anomaly_detect():
    return jsonify(ai.detect_anomalies(_anomaly_inputs()))


@bp.post("/query")
def natural_language_query():
    body = json_body()
    query = require_str(body, "query", max_length=1000)

    # The engine has six query handlers, reading `zones`, `providers`,
    # `stock_levels`, `zone_risks`, `forecasts` and `anomalies`. Supplying only
    # the first three left half the question types permanently answering
    # "no data available" regardless of what the database held.
    zone_inputs = _zone_inputs()
    history = queries.stock_history(limit=1000)

    context = {
        "zones": [
            {k: z[k] for k in ("zone_name", "total_requests", "pending_requests",
                               "avg_severity", "population_affected")}
            for z in zone_inputs
        ],
        "providers": [
            {
                "name": row["provider"],
                "total_allocations": row["total"],
                "success_rate": round(row["successful"] / max(1, row["total"]), 2),
            }
            for row in queries.provider_performance()
        ],
        "stock_levels": _stock_levels_for_insights(),
        "zone_risks": ai.predict_zone_risks(zone_inputs).get("zone_risks", []),
        "forecasts": ai.forecast_depletion(history).get("forecasts", []) if history else [],
        "anomalies": ai.detect_anomalies(_anomaly_inputs()).get("anomalies", []),
    }
    return jsonify(ai.answer_query(query, context))


@bp.post("/simulate")
def simulate():
    body = json_body()
    scenario = one_of(body, "scenario", SCENARIOS, "flood")
    population = optional_int(body, "population", 100_000,
                              minimum=POPULATION_RANGE[0], maximum=POPULATION_RANGE[1])

    current_stock: dict[str, float] = {}
    for row in queries.stock_totals_by_resource():
        key = _simulation_key(row["resource"])
        if key:
            current_stock[key] = current_stock.get(key, 0.0) + float(row["quantity"])

    return jsonify(ai.run_simulation(
        scenario=scenario,
        current_stock=current_stock or None,
        population=population,
    ))


@bp.get("/insights")
def insights():
    zone_risks = ai.predict_zone_risks(_zone_inputs()).get("zone_risks", [])
    history = queries.stock_history(limit=1000)
    forecasts = ai.forecast_depletion(history).get("forecasts", []) if history else []
    anomalies = ai.detect_anomalies(_anomaly_inputs()).get("anomalies", [])

    return jsonify(ai.generate_insights(
        forecasts=forecasts,
        zone_risks=zone_risks,
        anomalies=anomalies,
        stock_levels=_stock_levels_for_insights(),
    ))
