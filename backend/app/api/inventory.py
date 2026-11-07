"""Stock, requests and allocations.

This restores the feature the original had templates for but no routes:
`resource_requests.html`, `resource_stock.html` and `allocation_history.html`
all referenced endpoints (`allocate`, `resource_requests`,
`/recommend-allocation/<id>`) that had been removed from `app.py`, so every one
of those pages raised a BuildError or 404 on load.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..core.validation import json_body, one_of, optional_float, optional_int
from ..db import queries
from ..db.connection import has_core_tables
from ..services import allocation

bp = Blueprint("inventory", __name__)

REQUEST_STATUSES = ("pending", "allocated", "fulfilled", "rejected")

# Severity and urgency are multipliers on the priority formula; the schema
# constrains them to be positive, and anything past 3 is not meaningful.
SEVERITY_RANGE = (0.1, 3.0)
URGENCY_RANGE = (0.1, 3.0)


@bp.get("/stock")
def stock():
    low_only = request.args.get("low_only", "").lower() in {"1", "true", "yes"}
    rows = queries.stock_levels(low_only=low_only)
    return jsonify({
        "stock": rows,
        # Standing alerts, which are NOT the same as the is_low flag on each
        # row. is_low is recomputed from the current quantity on every
        # request; an alert is state the database raised when stock crossed
        # the threshold and will resolve when it recovers, so it knows WHEN
        # the shortage began.
        "alerts": queries.open_stock_alerts(),
        "available": True,
    })


@bp.get("/requests")
def list_requests():
    if not has_core_tables():
        return jsonify({"requests": [], "available": False})

    status = request.args.get("status")
    if status and status not in REQUEST_STATUSES:
        status = None
    limit = min(int(request.args.get("limit", 100) or 100), 500)
    return jsonify({"available": True, "requests": queries.list_requests(status=status, limit=limit)})


@bp.post("/requests")
def create_request():
    body = json_body()
    created = allocation.create_request(
        zone_id=optional_int(body, "zone_id", minimum=1),
        resource_id=optional_int(body, "resource_id", minimum=1),
        quantity=optional_float(body, "quantity_requested", minimum=0.01, maximum=1_000_000),
        severity=optional_float(body, "severity", 1.0, minimum=SEVERITY_RANGE[0], maximum=SEVERITY_RANGE[1]),
        urgency=optional_float(body, "urgency", 1.0, minimum=URGENCY_RANGE[0], maximum=URGENCY_RANGE[1]),
        population_affected=optional_int(body, "population_affected", 0, minimum=0, maximum=100_000_000),
    )
    return jsonify({"request": created}), 201


@bp.get("/requests/<int:request_id>/recommendation")
def recommend_allocation(request_id: int):
    """Suggested supplier split for a request. Read-only — nothing is committed."""
    return jsonify(allocation.recommend(request_id))


@bp.post("/requests/<int:request_id>/allocate")
def allocate(request_id: int):
    """Commit an allocation. Body may carry an explicit plan, or omit it to use
    the recommended one."""
    body = json_body() if request.data else {}
    plan = body.get("providers")
    if plan is not None and not isinstance(plan, list):
        plan = None
    return jsonify(allocation.execute(request_id, plan))


@bp.post("/requests/<int:request_id>/status")
def update_status(request_id: int):
    from ..core.errors import NotFoundError
    from ..db.connection import transaction

    body = json_body()
    status = one_of(body, "status", REQUEST_STATUSES)

    existing = queries.get_request(request_id)
    if not existing:
        raise NotFoundError(f"Request {request_id} does not exist.")

    with transaction() as conn:
        queries.set_request_status(request_id, status, conn)
        queries.log_audit("request_update", "Requests", request_id,
                          previous_value=existing["status"], new_value=status, conn=conn)

    return jsonify({"request": queries.get_request(request_id)})


@bp.get("/allocations")
def list_allocations():
    if not has_core_tables():
        return jsonify({"allocations": [], "available": False})
    limit = min(int(request.args.get("limit", 100) or 100), 500)
    return jsonify({"available": True, "allocations": queries.list_allocations(limit=limit)})


@bp.get("/logs")
def list_logs():
    if not has_core_tables():
        return jsonify({"logs": [], "available": False})
    limit = min(int(request.args.get("limit", 100) or 100), 500)
    return jsonify({"available": True, "logs": queries.system_logs(limit=limit)})
