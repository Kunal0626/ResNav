"""Search, NLP and input validation."""

from __future__ import annotations

import pytest

from app.services import nlp_engine
from app.services.embeddings import TfidfEncoder, build_encoder


def test_search_returns_ranked_results(client):
    body = client.post("/api/search", json={
        "query": "we urgently need clean drinking water",
        "latitude": 28.6139, "longitude": 77.2090,
    }).get_json()

    assert body["results"], "expected at least one provider"
    scores = [r["combined_score"] for r in body["results"]]
    assert scores == sorted(scores, reverse=True)


def test_search_returns_full_result_set(client):
    """Results used to be round-tripped through a 4 KB cookie session, which
    silently truncated anything beyond a handful of providers."""
    body = client.post("/api/search", json={"query": "medical help", "limit": 15}).get_json()
    assert len(body["results"]) > 3
    assert len(client.get("/api/explorer").get_json()["providers"]) >= len(body["results"])


def test_search_falls_back_to_default_location(client):
    body = client.post("/api/search", json={"query": "food"}).get_json()
    assert body["origin"]["fallback"] is True
    assert body["origin"]["latitude"] == pytest.approx(28.6139)


def test_zero_coordinates_do_not_rank_from_the_atlantic(client):
    """0/0 is a geolocation failure, not a real position off West Africa."""
    body = client.post("/api/search", json={
        "query": "shelter", "latitude": 0, "longitude": 0}).get_json()
    assert body["origin"]["latitude"] != 0


def test_maps_key_is_never_returned_to_the_client(client):
    body = client.post("/api/search", json={"query": "water"}).get_json()
    assert "google_maps_api_key" not in body


@pytest.mark.parametrize("payload,expected", [
    ({}, 422),
    ({"query": ""}, 422),
    ({"query": "x" * 5000}, 422),
    ({"query": "food", "latitude": 999}, 422),
])
def test_search_validates_input(client, payload, expected):
    assert client.post("/api/search", json=payload).status_code == expected


def test_search_requires_json_content_type(client):
    assert client.post("/api/search", data="query=food").status_code == 422


# ── NLP internals ───────────────────────────────────────────────────────────

def test_tfidf_encoder_produces_unit_vectors():
    encoder = TfidfEncoder()
    encoder.fit(["clean drinking water supply", "medical kits and bandages",
                 "temporary shelter and tents", "food rations and grain"])
    vectors = encoder.encode(["water"])
    assert vectors.shape[0] == 1
    assert abs(float((vectors[0] ** 2).sum()) - 1.0) < 1e-5


def test_encoder_falls_back_when_transformers_missing():
    """The old engine raised ImportError and 500ed the whole search."""
    encoder = build_encoder(prefer_transformers=True)
    assert encoder.name in ("tfidf", "sentence-transformers")


def test_quantity_and_urgency_extraction():
    result = nlp_engine.process("we urgently need 500 water packets immediately")
    assert result["extracted_quantity"] == 500
    assert result["urgency_score"] > 1.0


def test_empty_query_is_unknown_intent():
    assert nlp_engine.classify_intent("")["detected_intent"] == "unknown"


def test_navigation_event_returns_maps_url(client):
    body = client.post("/api/navigation-events", json={
        "latitude": 19.07, "longitude": 72.87, "provider_id": 1}).get_json()
    assert body["url"].startswith("https://www.google.com/maps/")
