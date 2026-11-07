"""Search orchestration: NLP intent + entity extraction, then hybrid ranking.

Steps:
  1. Run the NLP pipeline over the raw query (intent, urgency, quantity).
  2. Load providers and their stock.
  3. Rank semantically, weighted by stock, proximity and urgency.
  4. Record the (anonymised) query for analytics.
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.config import get_settings
from ..db import queries
from ..db.connection import table_exists
from . import geo, nlp_engine

log = logging.getLogger(__name__)


def run_search(query: str, user_lat: float, user_lon: float,
               *, limit: int | None = None) -> dict[str, Any]:
    """Return ranked providers plus the NLP metadata that explains the ranking."""
    settings = get_settings()
    limit = limit or settings.max_results

    nlp = nlp_engine.process(query)
    intent_label = (
        f"{nlp['detected_intent']} ({nlp['confidence_pct']}% confidence)"
        if nlp["detected_intent"] != "unknown"
        else "unknown"
    )

    providers = queries.load_providers_for_search()
    if not providers:
        return {"results": [], "intent": intent_label, "nlp": nlp, "total": 0}

    ranked = nlp_engine.rank_providers_semantic(
        query,
        providers,
        user_lat,
        user_lon,
        stock_by_provider=queries.stock_by_provider_and_resource(),
        urgency_score=nlp["urgency_score"],
    )

    results = [_serialise(p) for p in ranked[:limit]]

    # Analytics write is best-effort: a search must still return results if the
    # optional audit table is missing on this deployment.
    if table_exists("UserQuery"):
        try:
            queries.insert_user_query(query, intent_label, user_lat, user_lon)
        except Exception:
            log.warning("Failed to record user query for analytics.", exc_info=True)

    return {"results": results, "intent": intent_label, "nlp": nlp, "total": len(ranked)}


def _serialise(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": provider["id"],
        "name": provider["name"],
        "description": provider.get("description", ""),
        "phone": provider.get("phone"),
        "operating_hours": provider.get("operating_hours"),
        "is_24_7": bool(provider.get("is_24_7")),
        "address": provider.get("address"),
        "city": provider.get("city"),
        "state": provider.get("state"),
        "latitude": provider.get("latitude"),
        "longitude": provider.get("longitude"),
        "distance_km": round(provider.get("distance_km", 0.0), 2),
        "relevance_score": round(provider.get("semantic_score", 0.0), 3),
        "stock_availability": round(provider.get("total_stock", 0.0), 1),
        "combined_score": round(provider.get("hybrid_score", 0.0) * 100, 2),
        "why": provider.get("ranking_explanation", "Selected by AI."),
        "nav_url": geo.google_maps_nav_url(provider["latitude"], provider["longitude"]),
    }
