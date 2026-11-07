"""The request → recommend → allocate flow, including its failure modes.

This flow had no routes at all in the original codebase; the templates that
drove it pointed at endpoints that had been deleted.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def new_request(client, reference):
    payload = {
        "zone_id": reference["zones"][0]["id"],
        "resource_id": reference["resources"][0]["id"],
        "quantity_requested": 20,
        "severity": 2.0,
        "urgency": 2.0,
        "population_affected": 1000,
    }
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 201
    return response.get_json()["request"]


def test_create_request_computes_priority(new_request):
    assert new_request["status"] == "pending"
    assert new_request["priority_score"] > 0


def test_recommendation_covers_the_outstanding_quantity(client, new_request):
    body = client.get(f"/api/requests/{new_request['id']}/recommendation").get_json()
    assert body["allocation_type"] in ("single_provider", "split_allocation")
    planned = sum(leg["allocate_qty"] for leg in body["providers"])
    assert planned == pytest.approx(body["outstanding"], abs=0.01)


def test_allocation_deducts_stock_and_fulfils_the_request(client, new_request):
    plan = client.get(f"/api/requests/{new_request['id']}/recommendation").get_json()
    leg = plan["providers"][0]

    before = _stock_for(client, leg["provider_id"], new_request["resource_id"])
    result = client.post(f"/api/requests/{new_request['id']}/allocate", json={})
    assert result.status_code == 200

    body = result.get_json()
    assert body["status"] == "fulfilled"
    after = _stock_for(client, leg["provider_id"], new_request["resource_id"])
    assert after == pytest.approx(before - leg["allocate_qty"], abs=0.01)


def test_allocating_twice_conflicts(client, new_request):
    client.post(f"/api/requests/{new_request['id']}/allocate", json={})
    repeat = client.post(f"/api/requests/{new_request['id']}/allocate", json={})
    assert repeat.status_code == 409


def test_oversized_plan_is_rejected_before_any_write(client, new_request, reference):
    resource_id = new_request["resource_id"]
    provider_id = client.get(f"/api/requests/{new_request['id']}/recommendation") \
        .get_json()["providers"][0]["provider_id"]
    before = _stock_for(client, provider_id, resource_id)

    response = client.post(
        f"/api/requests/{new_request['id']}/allocate",
        json={"providers": [{"provider_id": provider_id, "allocate_qty": 10_000_000}]},
    )
    assert response.status_code == 422
    assert _stock_for(client, provider_id, resource_id) == before


def test_partial_plan_leaves_request_allocated_not_fulfilled(client, new_request):
    plan = client.get(f"/api/requests/{new_request['id']}/recommendation").get_json()
    leg = dict(plan["providers"][0])
    leg["allocate_qty"] = 5

    body = client.post(f"/api/requests/{new_request['id']}/allocate",
                       json={"providers": [leg]}).get_json()
    assert body["status"] == "allocated"
    assert body["request"]["quantity_allocated"] == pytest.approx(5)


def test_status_transition(client, new_request):
    body = client.post(f"/api/requests/{new_request['id']}/status",
                       json={"status": "rejected"}).get_json()
    assert body["request"]["status"] == "rejected"


def test_invalid_status_is_rejected(client, new_request):
    response = client.post(f"/api/requests/{new_request['id']}/status",
                           json={"status": "banana"})
    assert response.status_code == 422


def _stock_for(client, provider_id: int, resource_id: int) -> float:
    for row in client.get("/api/stock").get_json()["stock"]:
        if row["provider_id"] == provider_id and row["resource_id"] == resource_id:
            return float(row["quantity"])
    return 0.0
