"""All SQL for the application, grouped by the domain it serves.

Explicit SQL, no ORM — same choice the original made. What changed is that every
query here has a caller; the previous module carried ~15 selectors that nothing
referenced, plus a `get_category_id_to_resource_type_ids` that returned the same
list for every category regardless of input.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .connection import get_db, query_all, query_one, rows_to_dicts

Conn = sqlite3.Connection | None


# ─────────────────────────────────────────────────────────────────────────────
# Reference data
# ─────────────────────────────────────────────────────────────────────────────

def list_resources(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all(
        "SELECT id, name, unit, category FROM Resources ORDER BY name", (), conn))


def list_zones(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all(
        "SELECT id, zone_name AS name, region, state, population, risk_level "
        "FROM Zones ORDER BY zone_name", (), conn))


def list_providers(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT p.id, p.name, p.city, p.state, p.latitude, p.longitude,
               p.phone, p.is_24_7,
               COALESCE(SUM(sl.quantity), 0) AS total_stock
        FROM Providers p
        LEFT JOIN StockLevels sl ON sl.provider_id = p.id
        GROUP BY p.id
        ORDER BY p.name
    """, (), conn))


def list_emergency_contacts(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all(
        "SELECT name, number, scope FROM EmergencyContact ORDER BY scope, name", (), conn))


def load_providers_for_search(conn: Conn = None) -> list[dict[str, Any]]:
    """Providers with their offered services flattened into one text field.

    `services_text` is what the NLP ranker embeds, so the concatenation happens
    in SQL rather than in a Python loop over N+1 queries.
    """
    return rows_to_dicts(query_all("""
        SELECT p.id, p.name, p.description, p.phone, p.operating_hours, p.is_24_7,
               p.latitude, p.longitude, p.address, p.city, p.state,
               COALESCE(GROUP_CONCAT(c.name || ': ' || COALESCE(s.details, '')), '') AS services_text
        FROM Providers p
        LEFT JOIN ServicesOffered s ON s.provider_id = p.id
        LEFT JOIN ServiceCategory c ON s.category_id = c.id
        GROUP BY p.id
    """, (), conn))


def stock_by_provider_and_resource(conn: Conn = None) -> dict[tuple[int, int], float]:
    rows = query_all("SELECT provider_id, resource_id, quantity FROM StockLevels", (), conn)
    return {(r["provider_id"], r["resource_id"]): r["quantity"] for r in rows}


# ─────────────────────────────────────────────────────────────────────────────
# Overview / KPI
# ─────────────────────────────────────────────────────────────────────────────

def overview_stats(conn: Conn = None) -> dict[str, int]:
    """Five KPI counters in a single round trip instead of five separate ones."""
    row = query_one("""
        SELECT
          (SELECT COUNT(*) FROM Providers)                                          AS total_providers,
          (SELECT COALESCE(SUM(quantity), 0) FROM StockLevels)                      AS total_stock,
          (SELECT COUNT(*) FROM Requests WHERE status != 'fulfilled')               AS active_requests,
          (SELECT COUNT(*) FROM Requests WHERE status = 'pending')                  AS pending_allocations,
          (SELECT COUNT(*) FROM StockLevels WHERE quantity < low_stock_threshold)   AS low_stock_alerts
    """, (), conn)
    return {key: int(row[key] or 0) for key in row.keys()} if row else {}  # noqa: SIM118


def providers_with_stock(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT p.id, p.name, p.latitude, p.longitude, p.city,
               COALESCE(GROUP_CONCAT(DISTINCT r.name), 'N/A') AS resource_types,
               COALESCE(SUM(sl.quantity), 0) AS total_stock
        FROM Providers p
        LEFT JOIN StockLevels sl ON sl.provider_id = p.id
        LEFT JOIN Resources r ON sl.resource_id = r.id
        GROUP BY p.id
        ORDER BY total_stock DESC
    """, (), conn))


def recent_allocations(limit: int = 5, conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT a.id, z.zone_name AS zone, a.quantity_allocated AS quantity,
               res.name AS resource, p.name AS provider, a.allocated_at AS time
        FROM Allocations a
        JOIN Requests rq  ON a.request_id = rq.id
        JOIN Zones z      ON rq.zone_id = z.id
        JOIN Resources res ON a.resource_id = res.id
        JOIN Providers p  ON a.provider_id = p.id
        ORDER BY a.allocated_at DESC, a.id DESC
        LIMIT ?
    """, (limit,), conn))


def recent_requests(limit: int = 5, conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT rq.id, z.zone_name AS zone, rq.quantity_requested AS quantity,
               res.name AS resource, rq.status, rq.created_at AS time
        FROM Requests rq
        JOIN Zones z       ON rq.zone_id = z.id
        JOIN Resources res ON rq.resource_id = res.id
        ORDER BY rq.created_at DESC, rq.id DESC
        LIMIT ?
    """, (limit,), conn))


# ─────────────────────────────────────────────────────────────────────────────
# Inventory: stock, requests, allocations
# ─────────────────────────────────────────────────────────────────────────────

def stock_levels(conn: Conn = None, *, low_only: bool = False) -> list[dict[str, Any]]:
    sql = """
        SELECT sl.id, sl.provider_id, p.name AS provider_name,
               sl.resource_id, res.name AS resource_name, res.unit,
               sl.quantity, sl.low_stock_threshold AS threshold,
               CASE WHEN sl.quantity < sl.low_stock_threshold THEN 1 ELSE 0 END AS is_low,
               sl.updated_at
        FROM StockLevels sl
        JOIN Providers p   ON sl.provider_id = p.id
        JOIN Resources res ON sl.resource_id = res.id
    """
    if low_only:
        sql += " WHERE sl.quantity < sl.low_stock_threshold"
    sql += " ORDER BY is_low DESC, p.name, res.name"
    return rows_to_dicts(query_all(sql, (), conn))


def list_requests(conn: Conn = None, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    sql = """
        SELECT rq.id, rq.zone_id, z.zone_name AS zone,
               rq.resource_id, res.name AS resource, res.unit,
               rq.quantity_requested, rq.severity, rq.urgency,
               rq.population_affected, rq.priority_score, rq.status, rq.created_at,
               COALESCE((SELECT SUM(a.quantity_allocated) FROM Allocations a
                         WHERE a.request_id = rq.id), 0) AS quantity_allocated
        FROM Requests rq
        JOIN Zones z       ON rq.zone_id = z.id
        JOIN Resources res ON rq.resource_id = res.id
    """
    params: list[Any] = []
    if status:
        sql += " WHERE rq.status = ?"
        params.append(status)
    sql += " ORDER BY rq.priority_score DESC NULLS LAST, rq.created_at DESC LIMIT ?"
    params.append(limit)
    return rows_to_dicts(query_all(sql, params, conn))


def get_request(request_id: int, conn: Conn = None) -> dict[str, Any] | None:
    row = query_one("""
        SELECT rq.id, rq.zone_id, z.zone_name AS zone, rq.resource_id,
               res.name AS resource, rq.quantity_requested, rq.severity,
               rq.urgency, rq.population_affected, rq.priority_score, rq.status,
               COALESCE((SELECT SUM(a.quantity_allocated) FROM Allocations a
                         WHERE a.request_id = rq.id), 0) AS quantity_allocated
        FROM Requests rq
        JOIN Zones z       ON rq.zone_id = z.id
        JOIN Resources res ON rq.resource_id = res.id
        WHERE rq.id = ?
    """, (request_id,), conn)
    return dict(row) if row else None


def list_allocations(conn: Conn = None, limit: int = 100) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT a.id, a.request_id, a.provider_id, p.name AS provider_name,
               a.resource_id, res.name AS resource_name, res.unit,
               a.quantity_allocated AS quantity, a.allocated_at,
               z.zone_name AS zone, rq.status AS request_status
        FROM Allocations a
        JOIN Providers p   ON a.provider_id = p.id
        JOIN Resources res ON a.resource_id = res.id
        JOIN Requests rq   ON a.request_id = rq.id
        JOIN Zones z       ON rq.zone_id = z.id
        ORDER BY a.allocated_at DESC, a.id DESC
        LIMIT ?
    """, (limit,), conn))


def providers_holding_resource(resource_id: int, conn: Conn = None) -> list[dict[str, Any]]:
    """Candidate suppliers for a request, with the reliability signals the
    recommendation engine scores on."""
    return rows_to_dicts(query_all("""
        SELECT p.id, p.name, p.city, p.state, p.latitude, p.longitude,
               sl.quantity AS stock_level,
               COALESCE(perf.total, 0)   AS total_allocations,
               COALESCE(perf.success, 0) AS successful_allocations
        FROM StockLevels sl
        JOIN Providers p ON sl.provider_id = p.id
        LEFT JOIN (
            SELECT a.provider_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN rq.status IN ('allocated','fulfilled') THEN 1 ELSE 0 END) AS success
            FROM Allocations a
            JOIN Requests rq ON a.request_id = rq.id
            GROUP BY a.provider_id
        ) perf ON perf.provider_id = p.id
        WHERE sl.resource_id = ? AND sl.quantity > 0
        ORDER BY sl.quantity DESC
    """, (resource_id,), conn))


def get_stock_row(provider_id: int, resource_id: int, conn: Conn = None) -> dict[str, Any] | None:
    row = query_one(
        "SELECT id, quantity, low_stock_threshold FROM StockLevels "
        "WHERE provider_id = ? AND resource_id = ?",
        (provider_id, resource_id), conn)
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Writes — callers must wrap these in `transaction()`
# ─────────────────────────────────────────────────────────────────────────────

def insert_request(zone_id: int, resource_id: int, quantity: float, severity: float,
                   urgency: float, population_affected: int, priority_score: float,
                   conn: Conn = None) -> int:
    conn = conn or get_db()
    cur = conn.execute("""
        INSERT INTO Requests (zone_id, resource_id, quantity_requested, severity,
                              population_affected, urgency, priority_score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (zone_id, resource_id, quantity, severity, population_affected, urgency, priority_score))
    return int(cur.lastrowid)


def insert_allocation(request_id: int, provider_id: int, resource_id: int,
                      quantity: float, conn: Conn = None) -> int:
    conn = conn or get_db()
    cur = conn.execute("""
        INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
        VALUES (?, ?, ?, ?)
    """, (request_id, provider_id, resource_id, quantity))
    return int(cur.lastrowid)


def deduct_stock(provider_id: int, resource_id: int, quantity: float, conn: Conn = None) -> None:
    """Decrement stock, guarding against oversell at the SQL level.

    The WHERE clause makes the check and the write a single atomic statement, so
    two concurrent allocations cannot both read the same balance and both pass.
    """
    conn = conn or get_db()
    cur = conn.execute("""
        UPDATE StockLevels
        SET quantity = quantity - ?, updated_at = datetime('now')
        WHERE provider_id = ? AND resource_id = ? AND quantity >= ?
    """, (quantity, provider_id, resource_id, quantity))
    if cur.rowcount == 0:
        raise ValueError("insufficient_stock")


def set_request_status(request_id: int, status: str, conn: Conn = None) -> None:
    conn = conn or get_db()
    conn.execute(
        "UPDATE Requests SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, request_id))


def insert_stock_history(provider_id: int, resource_id: int, before: float, after: float,
                         change_type: str, details: str = "", conn: Conn = None) -> None:
    conn = conn or get_db()
    conn.execute("""
        INSERT INTO StockHistory (provider_id, resource_id, quantity_before,
                                  quantity_after, change_type, details)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (provider_id, resource_id, before, after, change_type, details))


def log_audit(action_type: str, table_name: str, record_id: int | None = None,
              previous_value: str | None = None, new_value: str | None = None,
              details: str | None = None, user: str = "system", conn: Conn = None) -> None:
    conn = conn or get_db()
    conn.execute("""
        INSERT INTO AuditLog (user, action_type, table_name, record_id,
                              previous_value, new_value, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user, action_type, table_name, record_id, previous_value, new_value, details))


def log_system_action(action: str, entity_type: str, entity_id: int = 0,
                      details: str = "", conn: Conn = None) -> None:
    conn = conn or get_db()
    conn.execute(
        "INSERT INTO SystemLog (action, entity_type, entity_id, details) VALUES (?, ?, ?, ?)",
        (action, entity_type, entity_id, details))


def insert_user_query(query_text: str, category_detected: str,
                      latitude: float | None = None, longitude: float | None = None,
                      conn: Conn = None) -> None:
    conn = conn or get_db()
    conn.execute(
        "INSERT INTO UserQuery (query_text_anon, category_detected, latitude, longitude) "
        "VALUES (?, ?, ?, ?)",
        (query_text[:500], category_detected, latitude, longitude))


# ─────────────────────────────────────────────────────────────────────────────
# Analytics / AI inputs
# ─────────────────────────────────────────────────────────────────────────────

def stock_history(limit: int = 1000, conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT sh.provider_id, p.name AS provider_name,
               sh.resource_id, res.name AS resource_name,
               sh.quantity_before, sh.quantity_after, sh.change_type, sh.created_at
        FROM StockHistory sh
        JOIN Providers p   ON sh.provider_id = p.id
        JOIN Resources res ON sh.resource_id = res.id
        ORDER BY sh.id ASC
        LIMIT ?
    """, (limit,), conn))


def stock_history_daily_totals(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT date(created_at) AS day, SUM(quantity_after) AS total
        FROM StockHistory
        WHERE created_at IS NOT NULL
        GROUP BY day
        ORDER BY day ASC
    """, (), conn))


def zone_metrics(conn: Conn = None) -> list[dict[str, Any]]:
    """Per-zone demand signals feeding the risk predictor.

    `stock_shortage_ratio` is computed here from real demand vs. supply. The old
    code hardcoded 0.5 for every zone, which made the risk model's most heavily
    weighted input a constant.
    """
    return rows_to_dicts(query_all("""
        SELECT z.zone_name,
               COUNT(rq.id)                                                  AS total_requests,
               COALESCE(SUM(CASE WHEN rq.status='pending' THEN 1 ELSE 0 END), 0) AS pending_requests,
               COALESCE(AVG(rq.severity), 1.0)                               AS avg_severity,
               COALESCE(AVG(rq.urgency), 1.0)                                AS avg_urgency,
               COALESCE(SUM(rq.population_affected), 0)                      AS population_affected,
               COALESCE(SUM(rq.quantity_requested), 0)                       AS total_demand,
               COALESCE(SUM(alloc.supplied), 0)                              AS total_supplied,
               z.risk_level
        FROM Zones z
        LEFT JOIN Requests rq ON rq.zone_id = z.id
        LEFT JOIN (
            SELECT request_id, SUM(quantity_allocated) AS supplied
            FROM Allocations GROUP BY request_id
        ) alloc ON alloc.request_id = rq.id
        GROUP BY z.id
        ORDER BY z.zone_name
    """, (), conn))


def provider_performance(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT p.name AS provider,
               COUNT(a.id) AS total,
               COALESCE(SUM(CASE WHEN rq.status IN ('allocated','fulfilled') THEN 1 ELSE 0 END), 0) AS successful
        FROM Providers p
        JOIN Allocations a ON a.provider_id = p.id
        JOIN Requests rq   ON a.request_id = rq.id
        GROUP BY p.id
        HAVING total > 0
        ORDER BY p.name
    """, (), conn))


def request_volume_by_resource(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT res.name AS resource, COUNT(rq.id) AS volume
        FROM Requests rq
        JOIN Resources res ON rq.resource_id = res.id
        GROUP BY res.id
        ORDER BY volume DESC
    """, (), conn))


def stock_totals_by_resource(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT res.name AS resource, COALESCE(SUM(sl.quantity), 0) AS quantity
        FROM Resources res
        LEFT JOIN StockLevels sl ON sl.resource_id = res.id
        GROUP BY res.id
        ORDER BY res.name
    """, (), conn))


def request_counts_by_status(conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all(
        "SELECT status, COUNT(*) AS count FROM Requests GROUP BY status ORDER BY status", (), conn))


def system_logs(limit: int = 100, conn: Conn = None) -> list[dict[str, Any]]:
    return rows_to_dicts(query_all("""
        SELECT id, user, timestamp, action_type, table_name, record_id, details
        FROM AuditLog
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
    """, (limit,), conn))
