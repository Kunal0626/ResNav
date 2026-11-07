"""Allocation planning and execution.

The original codebase had a recommendation function but no route to reach it and
no code path that actually moved stock — `templates/resource_requests.html`
posted to endpoints that did not exist. This module completes the flow:
recommend a plan, then commit it atomically.
"""

from __future__ import annotations

import logging
from typing import Any

from pymysql.err import MySQLError

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..db import queries
from ..db.connection import call_proc, query_one, transaction

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
    """Commit an allocation by calling sp_allocate_request.

    This function used to do the work itself: loop over the plan, deduct
    stock with a conditional UPDATE, insert the allocation rows, write the
    history and move the request status -- all from Python, inside one
    transaction. On SQLite that was safe, but only by accident: BEGIN
    IMMEDIATE takes a database-wide write lock, so there was never a second
    writer to race with.

    InnoDB has row-level locking and many concurrent writers, so the gap
    between `recommend()` reading the balances and `execute()` acting on them
    is a real race: two sessions can both read the same stock and both commit
    against it. Keeping the Python loop and merely changing the driver would
    have introduced an oversell bug that SQLite had been hiding.

    So the decision moved into the database. sp_allocate_request takes every
    lock it needs up front in primary-key order, re-reads the quantities
    AFTER holding them, and only then allocates -- nearest centre first, by
    real haversine distance. Phase 6 demonstrates the race against a
    deliberately unlocked variant.

    The `plan` argument is accepted and ignored for allocation purposes: the
    database now chooses the suppliers, because choosing them in Python means
    choosing them from stale numbers. It is still validated, so a caller
    asking for more than is outstanding gets the same error it always did.
    """
    request = queries.get_request(request_id)
    if not request:
        raise NotFoundError(f"Request {request_id} does not exist.")
    if request["status"] in ("fulfilled", "rejected"):
        raise ConflictError(f"Request {request_id} is already {request['status']}.")

    outstanding = float(request["quantity_requested"]) - float(request["quantity_allocated"])

    # A caller may cap HOW MUCH is dispatched -- the API has always allowed
    # a partial dispatch -- but no longer chooses WHICH centres supply it.
    # Picking suppliers in the client means picking them from quantities read
    # before any lock was taken, which is exactly the race described above.
    cap = 0.0
    if plan:
        cap = sum(float(leg.get("allocate_qty") or 0) for leg in plan)
        if cap <= 0:
            raise ValidationError("Allocation plan must move a positive quantity.")
        if cap > outstanding + FULL_COVERAGE_EPSILON:
            raise ValidationError(
                f"Plan allocates {cap} but only {round(outstanding, 2)} is outstanding.")

    try:
        # The procedure runs its own transaction and COMMITs, so there is no
        # outer transaction() here -- wrapping it would be a lie.
        out = call_proc(
            "sp_allocate_request",
            (request_id, cap),
            ("@allocated", "@legs", "@status"),
        )
    except MySQLError as exc:
        raise _translate(exc) from None

    allocated = float(out.get("allocated") or 0)
    if allocated <= 0:
        raise ConflictError(
            f"No provider currently holds stock of '{request['resource']}'.")

    updated = queries.get_request(request_id)
    allocation_ids = [row["id"] for row in queries.allocations_for_request(request_id)]

    log.info("Allocated %.2f units for request %s (%s).",
             allocated, request_id, updated["status"])
    return {
        "request_id": request_id,
        "status": updated["status"],
        "allocated": round(allocated, 2),
        "allocation_ids": allocation_ids,
        "request": updated,
    }


def cancel(request_id: int) -> dict[str, Any]:
    """Release every active allocation and return the stock, atomically."""
    if not queries.get_request(request_id):
        raise NotFoundError(f"Request {request_id} does not exist.")
    try:
        out = call_proc("sp_cancel_request", (request_id,), ("@released", "@legs"))
    except MySQLError as exc:
        raise _translate(exc) from None
    return {
        "request_id": request_id,
        "released": float(out.get("released") or 0),
        "legs": int(out.get("legs") or 0),
        "request": queries.get_request(request_id),
    }


def restock(provider_id: int, resource_id: int, quantity: float) -> dict[str, Any]:
    """Add stock to a centre."""
    try:
        out = call_proc("sp_restock_center",
                        (provider_id, resource_id, quantity), ("@new_total",))
    except MySQLError as exc:
        raise _translate(exc) from None
    return {
        "provider_id": provider_id,
        "resource_id": resource_id,
        "new_total": float(out.get("new_total") or 0),
    }


# The guards raise SIGNAL SQLSTATE '45000' with a machine-readable prefix
# ("insufficient_stock: ..."), so the API can keep returning the same error
# codes it always did instead of leaking SQL text to the browser.
_SIGNAL_TO_ERROR: dict[str, type[Exception]] = {
    "stock_negative": ConflictError,
    "insufficient_stock": ConflictError,
    "no_stock_row": ConflictError,
    "request_closed": ConflictError,
    "already_cancelled": ConflictError,
    "over_allocation": ValidationError,
    "bad_quantity": ValidationError,
    "not_found": NotFoundError,
}


def _translate(exc: Exception) -> Exception:
    """Turn a database error into the API's own error vocabulary.

    MySQL errno 1644 is a user-raised SIGNAL -- one of our guards. Anything
    else is a genuine database fault and is re-raised untouched so it is
    logged with a traceback rather than shown to a user as a 409.
    """
    errno = exc.args[0] if exc.args else None
    message = str(exc.args[1]) if len(exc.args) > 1 else str(exc)

    if errno == 1644:
        tag, _, detail = message.partition(":")
        factory = _SIGNAL_TO_ERROR.get(tag.strip())
        if factory is not None:
            return factory(detail.strip() or message)
        return ConflictError(message)
    if errno == 3819:  # CHECK constraint violated
        return ValidationError(f"The database rejected that value: {message}")
    return exc


def create_request(*, zone_id: int, resource_id: int, quantity: float, severity: float,
                   urgency: float, population_affected: int) -> dict[str, Any]:
    """Create a resource request, computing its priority score.

    priority = severity × population × urgency ÷ current total stock — scarce
    resources for large, severe incidents rise to the top of the queue.
    """
    if not query_one("SELECT 1 AS ok FROM Zones WHERE id = %s", (zone_id,)):
        raise ValidationError("Unknown zone.", details={"field": "zone_id"})
    if not query_one("SELECT 1 AS ok FROM Resources WHERE id = %s", (resource_id,)):
        raise ValidationError("Unknown resource.", details={"field": "resource_id"})

    total_stock = query_one(
        "SELECT COALESCE(SUM(quantity), 0) AS total FROM StockLevels WHERE resource_id = %s",
        (resource_id,))["total"]
    priority = round(
        (severity * max(population_affected, 1) * urgency) / max(1.0, float(total_stock)), 4)

    with transaction() as conn:
        request_id = queries.insert_request(
            zone_id, resource_id, quantity, severity, urgency, population_affected,
            priority, conn)
        queries.log_audit("request_create", "Requests", request_id,
                          new_value=f"{quantity} units", details="request created", conn=conn)

    return queries.get_request(request_id)
