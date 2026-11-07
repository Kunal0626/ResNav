"""Search and navigation endpoints.

The old flow ran a POST, stashed the entire result list in the Flask *cookie*
session, then redirected to a page that read it back. Cookie sessions cap at
about 4 KB, so any result set over roughly three providers was silently dropped
before it ever reached the browser. Search now returns its results directly.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from ..core.config import get_settings
from ..core.validation import coordinates, json_body, optional_int, require_str
from ..db import queries
from ..db.connection import table_exists, transaction
from ..services import geo, search_service

log = logging.getLogger(__name__)

bp = Blueprint("search", __name__)

# Central Delhi. Used when the browser denies or fails geolocation, so ranking
# still has a reference point instead of falling back to 0,0 in the Atlantic.
DEFAULT_LOCATION = (28.6139, 77.2090)


@bp.post("/search")
def search():
    body = json_body()
    query = require_str(body, "query", max_length=500)
    lat, lon = coordinates(body, default=DEFAULT_LOCATION)
    limit = optional_int(body, "limit", get_settings().max_results, minimum=1, maximum=100)
    used_fallback = (lat, lon) == DEFAULT_LOCATION and not body.get("latitude")

    with transaction():
        outcome = search_service.run_search(query, lat, lon, limit=limit)

    results = outcome["results"]
    settings = get_settings()

    # Build the embed URL server-side so the Maps key never reaches the client.
    map_embed_url = None
    if results and settings.google_maps_api_key:
        first = results[0]
        map_embed_url = geo.google_maps_embed_directions_url(
            lat, lon, first["latitude"], first["longitude"], settings.google_maps_api_key)

    return jsonify({
        "query": query,
        "results": results,
        "total": outcome["total"],
        "detected_intent": outcome["intent"],
        "nlp": outcome["nlp"],
        "confidence": outcome["nlp"]["confidence_pct"],
        "origin": {"latitude": lat, "longitude": lon, "fallback": used_fallback},
        "map_embed_url": map_embed_url,
        "emergency_contacts": queries.list_emergency_contacts() if table_exists("EmergencyContact") else [],
    })


@bp.post("/navigation-events")
def record_navigation():
    """Record a 'navigate to provider' click and hand back the Maps deep link.

    Previously this was a GET that issued a 302 to Google. As an API it returns
    the URL instead, so the frontend controls whether to open a tab — and a
    logging failure can no longer strand the user on a redirect that never fires.
    """
    body = json_body()
    lat, lon = coordinates(body)
    provider_id = optional_int(body, "provider_id", 0, minimum=0)

    if table_exists("SystemLog"):
        try:
            with transaction():
                queries.log_system_action(
                    "navigation_click", "Provider", provider_id or 0, f"lat={lat},lon={lon}")
        except Exception:
            log.warning("Failed to record navigation click.", exc_info=True)

    return jsonify({"url": geo.google_maps_nav_url(lat, lon)})
