-- ===========================================================================
-- 01_views.sql
--
-- ResNav shipped twelve views and used none of them (docs/MAPPING.md finding
-- 1): the Python layer recomputed all of it. These are written to be USED --
-- Phase 4 points the API at them -- which is the difference between a schema
-- that demonstrates SQL and one that merely contains it.
--
-- Every view satisfies ONLY_FULL_GROUP_BY, which this server enforces: each
-- non-aggregated column in the select list appears in GROUP BY, or is
-- functionally dependent on something that does.
--
-- Views that touch Allocations filter status = 'active'. Released allocations
-- are kept on record, so a forgotten filter double-counts returned stock.
-- Putting the filter here means ordinary queries cannot get it wrong.
-- ===========================================================================

DROP VIEW IF EXISTS v_center_stock_summary;
DROP VIEW IF EXISTS v_low_stock;
DROP VIEW IF EXISTS v_provider_reliability;
DROP VIEW IF EXISTS v_request_fulfilment;
DROP VIEW IF EXISTS v_zone_shortage_analysis;
DROP VIEW IF EXISTS v_high_risk_zones;
DROP VIEW IF EXISTS v_fastest_depleting_resources;
DROP VIEW IF EXISTS v_provider_efficiency;
DROP VIEW IF EXISTS v_allocation_performance;


-- What does every centre hold, and is it short?
-- Column names match what /api/stock already returns, so the port is a
-- change of FROM clause rather than a change of contract.
CREATE VIEW v_center_stock_summary AS
SELECT sl.id                AS id,
       sl.provider_id       AS provider_id,
       p.name               AS provider_name,
       p.city               AS city,
       p.state              AS state,
       sl.resource_id       AS resource_id,
       r.name               AS resource_name,
       r.unit               AS unit,
       sl.quantity          AS quantity,
       sl.low_stock_threshold AS threshold,
       (sl.quantity < sl.low_stock_threshold) AS is_low,
       sl.updated_at        AS updated_at
FROM StockLevels sl
JOIN Providers p ON p.id = sl.provider_id
JOIN Resources r ON r.id = sl.resource_id;


-- Only the short lines, plus the open alert if one is standing.
CREATE VIEW v_low_stock AS
SELECT s.*,
       a.id          AS alert_id,
       a.raised_at   AS alert_raised_at,
       (s.threshold - s.quantity) AS shortfall
FROM v_center_stock_summary s
LEFT JOIN StockAlerts a
       ON a.provider_id = s.provider_id
      AND a.resource_id = s.resource_id
      AND a.status = 'open'
WHERE s.quantity < s.threshold;


-- Reliability: what fraction of a centre's allocations ended up on a request
-- that was actually served. The allocator inlines this subquery today, on
-- every single call; naming it makes the intent legible and gives Phase 9
-- something to run EXPLAIN against.
--
-- A centre with no history scores 0.7, not 0 -- see the note in
-- services/allocation.py: a zero would bury every new centre permanently.
-- The constant lives here now, beside the data it describes.
CREATE VIEW v_provider_reliability AS
SELECT p.id   AS provider_id,
       p.name AS provider_name,
       COUNT(a.id) AS total_allocations,
       COALESCE(SUM(rq.status IN ('allocated','fulfilled')), 0) AS successful_allocations,
       CASE WHEN COUNT(a.id) = 0 THEN 0.7000
            ELSE ROUND(COALESCE(SUM(rq.status IN ('allocated','fulfilled')), 0)
                       / COUNT(a.id), 4)
       END AS reliability
FROM Providers p
LEFT JOIN Allocations a ON a.provider_id = p.id AND a.status = 'active'
LEFT JOIN Requests   rq ON rq.id = a.request_id
GROUP BY p.id, p.name;


-- How much of each request is actually met. get_request() inlines this
-- correlated SUM today.
CREATE VIEW v_request_fulfilment AS
SELECT rq.id                 AS request_id,
       rq.zone_id            AS zone_id,
       z.zone_name           AS zone,
       rq.resource_id        AS resource_id,
       r.name                AS resource,
       r.unit                AS unit,
       rq.quantity_requested AS quantity_requested,
       COALESCE(SUM(a.quantity_allocated), 0) AS quantity_allocated,
       rq.quantity_requested - COALESCE(SUM(a.quantity_allocated), 0) AS outstanding,
       ROUND(COALESCE(SUM(a.quantity_allocated), 0) / rq.quantity_requested, 4)
                             AS fulfilment_ratio,
       rq.severity, rq.urgency, rq.population_affected,
       rq.priority_score, rq.status, rq.created_at, rq.closed_at,
       TIMESTAMPDIFF(HOUR, rq.created_at, COALESCE(rq.closed_at, NOW(6)))
                             AS age_hours
FROM Requests rq
JOIN Zones     z ON z.id = rq.zone_id
JOIN Resources r ON r.id = rq.resource_id
LEFT JOIN Allocations a ON a.request_id = rq.id AND a.status = 'active'
GROUP BY rq.id, rq.zone_id, z.zone_name, rq.resource_id, r.name, r.unit,
         rq.quantity_requested, rq.severity, rq.urgency, rq.population_affected,
         rq.priority_score, rq.status, rq.created_at, rq.closed_at;


-- Unmet demand per zone.
CREATE VIEW v_zone_shortage_analysis AS
SELECT z.id              AS zone_id,
       z.zone_name       AS zone_name,
       z.state           AS state,
       z.risk_level      AS risk_level,
       z.population      AS population,
       COUNT(DISTINCT f.request_id) AS total_requests,
       COALESCE(SUM(f.quantity_requested), 0) AS total_requested,
       COALESCE(SUM(f.quantity_allocated), 0) AS total_allocated,
       COALESCE(SUM(f.outstanding), 0)        AS total_outstanding,
       CASE WHEN COALESCE(SUM(f.quantity_requested), 0) = 0 THEN 0
            ELSE ROUND(1 - SUM(f.quantity_allocated) / SUM(f.quantity_requested), 4)
       END AS shortage_ratio
FROM Zones z
LEFT JOIN v_request_fulfilment f ON f.zone_id = z.id
GROUP BY z.id, z.zone_name, z.state, z.risk_level, z.population;


-- Zones where the gap is material. HAVING, not WHERE: the condition is on an
-- aggregate, which WHERE cannot see.
CREATE VIEW v_high_risk_zones AS
SELECT *
FROM v_zone_shortage_analysis
WHERE total_requests > 0
  AND shortage_ratio > 0.3;


-- Which resource lines are draining fastest, from real movement history.
-- Window function: rank each resource within its own provider.
CREATE VIEW v_fastest_depleting_resources AS
SELECT sl.provider_id,
       p.name  AS provider_name,
       sl.resource_id,
       r.name  AS resource_name,
       sl.quantity AS quantity_now,
       COALESCE(h.consumed, 0) AS consumed_total,
       COALESCE(h.movements, 0) AS movements,
       CASE WHEN COALESCE(h.consumed, 0) = 0 THEN NULL
            ELSE ROUND(sl.quantity / (h.consumed / GREATEST(h.movements, 1)), 2)
       END AS cover_remaining,
       RANK() OVER (PARTITION BY sl.provider_id
                    ORDER BY COALESCE(h.consumed, 0) DESC) AS depletion_rank
FROM StockLevels sl
JOIN Providers p ON p.id = sl.provider_id
JOIN Resources r ON r.id = sl.resource_id
LEFT JOIN (
    SELECT provider_id, resource_id,
           SUM(quantity_before - quantity_after) AS consumed,
           COUNT(*) AS movements
    FROM StockHistory
    WHERE change_type = 'allocation'
    GROUP BY provider_id, resource_id
) h ON h.provider_id = sl.provider_id AND h.resource_id = sl.resource_id;


-- Centres ranked by how much they have supplied and how reliably.
CREATE VIEW v_provider_efficiency AS
SELECT rel.provider_id,
       rel.provider_name,
       rel.total_allocations,
       rel.successful_allocations,
       rel.reliability,
       COALESCE(sup.units_supplied, 0) AS units_supplied,
       COALESCE(stk.units_held, 0)     AS units_held,
       RANK() OVER (ORDER BY COALESCE(sup.units_supplied, 0) DESC) AS supply_rank
FROM v_provider_reliability rel
LEFT JOIN (
    SELECT provider_id, SUM(quantity_allocated) AS units_supplied
    FROM Allocations WHERE status = 'active' GROUP BY provider_id
) sup ON sup.provider_id = rel.provider_id
LEFT JOIN (
    SELECT provider_id, SUM(quantity) AS units_held
    FROM StockLevels GROUP BY provider_id
) stk ON stk.provider_id = rel.provider_id;


-- Fulfilment rate overall and per resource, with a ROLLUP total row.
-- The GROUPING() call is what distinguishes a genuine NULL from the one
-- ROLLUP inserts for the subtotal line.
CREATE VIEW v_allocation_performance AS
SELECT CASE WHEN GROUPING(r.name) = 1 THEN 'ALL RESOURCES' ELSE r.name END AS resource_name,
       COUNT(DISTINCT rq.id)                        AS requests,
       SUM(rq.status = 'fulfilled')                 AS fulfilled,
       SUM(rq.status = 'rejected')                  AS rejected,
       SUM(rq.status IN ('pending','allocated'))    AS still_open,
       ROUND(SUM(rq.status = 'fulfilled') / COUNT(DISTINCT rq.id), 4) AS fulfilment_rate
FROM Requests rq
JOIN Resources r ON r.id = rq.resource_id
GROUP BY r.name WITH ROLLUP;
