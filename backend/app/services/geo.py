"""Geospatial helpers and Google Maps URL construction.

The Maps Embed key is used here, server-side, and only ever leaves as a fully
formed embed URL. It is never sent to the frontend as a bare value, so it cannot
be lifted out of a JS bundle. Restrict the key by HTTP referrer in the Google
Cloud console as well.
"""

from __future__ import annotations

import math
from urllib.parse import urlencode

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def proximity_score(distance_km: float | None, scale_km: float = 10.0) -> float:
    """Exponential distance decay in [0, 1]; ~0.37 at `scale_km`."""
    if distance_km is None or distance_km < 0:
        return 0.0
    return math.exp(-distance_km / scale_km)


def google_maps_nav_url(lat: float, lon: float) -> str:
    """Deep link that drops a pin at the destination, from which users can route."""
    return "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": f"{lat},{lon}"})


def google_maps_embed_directions_url(origin_lat: float, origin_lon: float,
                                     dest_lat: float, dest_lon: float,
                                     api_key: str | None) -> str | None:
    """Embeddable directions iframe URL, or None when no key is configured."""
    if not api_key or not api_key.strip():
        return None
    params = urlencode({
        "key": api_key.strip(),
        "origin": f"{origin_lat},{origin_lon}",
        "destination": f"{dest_lat},{dest_lon}",
        "mode": "driving",
    })
    return f"https://www.google.com/maps/embed/v1/directions?{params}"
