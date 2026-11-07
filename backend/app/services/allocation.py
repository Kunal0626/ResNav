"""Allocation planning and execution.

The original codebase had a recommendation function but no route to reach it and
no code path that actually moved stock — `templates/resource_requests.html`
posted to endpoints that did not exist. This module completes the flow:
recommend a plan, then commit it atomically.
"""

from __future__ import annotations

import logging
from typing import Any

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..db import queries
from ..db.connection import get_db, transaction

log = logging.getLogger(__name__)

# Scoring weights, mirroring the search ranker so the two feel consistent.
W_COVERAGE, W_RELIABILITY, W_LOCALITY, W_URGENCY = 0.4, 0.3, 0.2, 0.1

# Below this, splitting across providers is preferred over a single supplier.
FULL_COVERAGE_EPSILON = 0.001


def _score_provider(provider: dict[str, Any], *, quantity: float, urgency: float,
                    zone_state: str | None) -> dict[str, Any]:
    """Rank a candidate supplier for one request.

    Coverage is how much of the request they can meet; reliability is their
    historical fulfilment rate; locality rewards same-state providers.

    Zones carry no coordinates in the schema, so proximity is approximated by
    state match rather than the previous code's distance-from-Delhi, which
    scored every provider against a fixed point unrelated to the request.
    """
    stock = float(provider.get("stock_level") or 0.0)
    total = int(provider.get("total_allocations") or 0)
    successful = int(provider.get("successful_allocations") or 0)

    coverage = min(1.0, stock / max(quantity, 1.0))
    # No history yet is treated as neutral-positive rather than a zero, so new
    # providers are not permanently buried below established ones.
    reliability = (successful / total) if total > 0 else 0.7
    locality = 1.0 if zone_state and provider.get("state") == zone_state else 0.4
    urgency_weight = min(1.0, urgency / 3.0)

    score = (
        W_COVERAGE * coverage
        + W_RELIABILITY * reliability
        + W_LOCALITY * locality
        + W_URGENCY * urgency_weight
    )

    reasons = []
    if coverage >= 1.0:
        reasons.append("can fulfil in full")
    elif coverage > 0.5:
        reasons.append(f"covers {coverage:.0%} of the request")
    if reliability >= 0.8:
        reasons.append(f"{reliability:.0%} historical fulfilment")
    if locality > 0.5:
        reasons.append("same state as the requesting zone")
    if urgency_weight > 0.5:
        reasons.append("prioritised for urgency")

    return {
        "provider_id": provider["id"],
        "provider_name": provider["name"],
        "provider_city": provider.get("city"),
        "provider_stock": round(stock, 2),
        "coverage": round(coverage, 3),
        "reliability": round(reliability, 3),
        "score": round(score, 4),
        "reasoning": ", ".join(reasons) or "available stock on hand",
    }


def recommend(request_id: int) -> dict[str, Any]:
    """Build an allocation plan for a request without writing anything."""
    request = queries.get_request(request_id)
    if not request:
        raise NotFoundError(f"Request {request_id} does not exist.")

    outstanding = float(request["quantity_requested"]) - float(request["quantity_allocated"])
    if outstanding <= FULL_COVERAGE_EPSILON:
        return {
            "request_id": request_id,
            "resource_name": request["resource"],
            "quantity_requested": request["quantity_requested"],
            "outstanding": 0,
            "allocation_type": "already_fulfilled",
            "providers": [],
            "message": "This request has already been fully allocated.",
        }

    zone_row = next((z for z in queries.list_zones() if z["id"] == request["zone_id"]), None)
    zone_state = zone_row.get("state") if zone_row else None

    candidates = queries.providers_holding_resource(request["resource_id"])
    if not candidates:
        return {
            "request_id": request_id,
            "resource_name": request["resource"],
            "quantity_requested": request["quantity_requested"],
            "outstanding": round(outstanding, 2),
            "allocation_type": "no_supply",
            "providers": [],
            "total_available": 0,
            "shortage": round(outstanding, 2),
            "coverage_pct": 0.0,
            "message": f"No provider currently holds stock of '{request['resource']}'.",
        }

    scored = sorted(
        (_score_provider(c, quantity=outstanding, urgency=float(request["urgency"]),
                         zone_state=zone_state) for c in candidates),
        key=lambda s: s["score"],
        reverse=True,
    )

    total_available = sum(s["provider_stock"] for s in scored)
    best = scored[0]

    # Greedily draw from the highest-scoring providers until the request is met.
    plan: list[dict[str, Any]] = []
    remaining = outstanding
    for supplier in scored:
        if remaining <= FULL_COVERAGE_EPSILON:
            break
        take = min(supplier["provider_stock"], remaining)
        if take <= 0:
            continue
        remaining -= take
        plan.append({
            **supplier,
            "allocate_qty": round(take, 2),
            "remaining_after": round(supplier["provider_stock"] - take, 2),
        })

    shortage = round(max(0.0, remaining), 2)
    covered = outstanding - shortage
    coverage_pct = round((covered / outstanding) * 100, 1) if outstanding else 100.0
    single = len(plan) == 1 and shortage <= FULL_COVERAGE_EPSILON

    confidence = min(99, int(best["score"] * 100 * (1.0 if single else 0.8)))

    return {
        "request_id": request_id,
        "zone": request["zone"],
        "resource_name": request["resource"],
        "quantity_requested": request["quantity_requested"],
        "outstanding": round(outstanding, 2),
        "allocation_type": "single_provider" if single else "split_allocation",
        "providers": plan,
        "total_available": round(total_available, 2),
        "fully_satisfiable": shortage <= FULL_COVERAGE_EPSILON,
        "coverage_pct": coverage_pct,
        "shortage": shortage,
        "confidence_score": confidence,
        "message": (
            f"Recommended: {best['provider_name']} — {best['reasoning']}."
            if single else
            f"Split across {len(plan)} providers to reach {coverage_pct}% coverage."
        ),
    }


def execute(request_id: int, plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Commit an allocation plan: deduct stock, record allocations, update status.

    Everything runs inside one transaction. A shortfall on any leg rolls the
    whole allocation back rather than leaving stock deducted with no matching
    Allocations row.
    """
    request = queries.get_request(request_id)
    if not request:
        raise NotFoundError(f"Request {request_id} does not exist.")
    if request["status"] in ("fulfilled", "rejected"):
        raise ConflictError(f"Request {request_id} is already {request['status']}.")

    if plan is None:
        recommendation = recommend(request_id)
        plan = recommendation["providers"]
        if not plan:
            raise ConflictError(recommendation.get("message", "No allocation is possible."))

    resource_id = request["resource_id"]
    outstanding = float(request["quantity_requested"]) - float(request["quantity_allocated"])
    requested_total = sum(float(leg["allocate_qty"]) for leg in plan)
    if requested_total <= 0:
        raise ValidationError("Allocation plan must move a positive quantity.")
    if requested_total > outstanding + FULL_COVERAGE_EPSILON:
        raise ValidationError(
            f"Plan allocates {requested_total} but only {round(outstanding, 2)} is outstanding.")

    allocated_ids: list[int] = []
    with transaction() as conn:
        for leg in plan:
            provider_id = int(leg["provider_id"])
            quantity = float(leg["allocate_qty"])
            if quantity <= 0:
                continue

            before = queries.get_stock_row(provider_id, resource_id, conn)
            if before is None:
                raise ConflictError(
                    f"Provider {provider_id} holds no stock record for this resource.")

            try:
                queries.deduct_stock(provider_id, resource_id, quantity, conn)
            except ValueError:
                raise ConflictError(
                    f"{leg.get('provider_name', f'Provider {provider_id}')} no longer has "
                    f"{quantity} units available."
                ) from None

            allocated_ids.append(
                queries.insert_allocation(request_id, provider_id, resource_id, quantity, conn))
            queries.insert_stock_history(
                provider_id, resource_id,
                before["quantity"], before["quantity"] - quantity,
                "allocation", f"request #{request_id}", conn)

        total_after = float(request["quantity_allocated"]) + requested_total
        status = "fulfilled" if total_after >= float(request["quantity_requested"]) - FULL_COVERAGE_EPSILON else "allocated"
        queries.set_request_status(request_id, status, conn)
        queries.log_audit("allocation", "Allocations", request_id,
                          previous_value=request["status"], new_value=status,
                          details=f"{requested_total} units across {len(plan)} provider(s)",
                          conn=conn)

    log.info("Allocated %.2f units for request %s (%s).", requested_total, request_id, status)
    return {
        "request_id": request_id,
        "status": status,
        "allocated": round(requested_total, 2),
        "allocation_ids": allocated_ids,
        "request": queries.get_request(request_id),
    }


def create_request(*, zone_id: int, resource_id: int, quantity: float, severity: float,
                   urgency: float, population_affected: int) -> dict[str, Any]:
    """Create a resource request, computing its priority score.

    priority = severity × population × urgency ÷ current total stock — scarce
    resources for large, severe incidents rise to the top of the queue.
    """
    conn = get_db()
    if not queries.query_one("SELECT 1 FROM Zones WHERE id = ?", (zone_id,), conn):
        raise ValidationError("Unknown zone.", details={"field": "zone_id"})
    if not queries.query_one("SELECT 1 FROM Resources WHERE id = ?", (resource_id,), conn):
        raise ValidationError("Unknown resource.", details={"field": "resource_id"})

    total_stock = queries.query_one(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM StockLevels WHERE resource_id = ?",
        (resource_id,), conn)["total"]
    priority = round((severity * max(population_affected, 1) * urgency) / max(1.0, float(total_stock)), 4)

    with transaction(conn):
        request_id = queries.insert_request(
            zone_id, resource_id, quantity, severity, urgency, population_affected, priority, conn)
        queries.log_audit("request_create", "Requests", request_id,
                          new_value=f"{quantity} units", details="request created", conn=conn)

    return queries.get_request(request_id)
