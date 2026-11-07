-- =============================================================================
-- ResNav Enterprise DBMS — Unified Database Schema (Full Reconstruction)
-- =============================================================================
-- Architecture demonstrating:
--   ✓ ACID Transactions      ✓ Triggers           ✓ Stored Procedures
--   ✓ Views (Analytical)     ✓ Window Functions   ✓ Audit Logging
--   ✓ Data Integrity (FK, NOT NULL, CHECK, UNIQUE)
--   ✓ Risk Materialization   ✓ Concurrency Safety ✓ Aggregation Logic
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;


-- #############################################################################
-- SECTION 1 — 12 CORE DBMS TABLES
-- #############################################################################

-- ─── T1: Resources ──────────────────────────────────────────────────────────
-- Normalized resource type catalog
CREATE TABLE IF NOT EXISTS Resources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    unit        TEXT    NOT NULL DEFAULT 'units',
    category    TEXT    NOT NULL DEFAULT 'general',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_resources_category ON Resources(category);

-- ─── T2: Providers ──────────────────────────────────────────────────────────
-- Service providers (NGOs, hospitals, shelters, government offices)
CREATE TABLE IF NOT EXISTS Providers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    address         TEXT,
    city            TEXT    NOT NULL,
    state           TEXT    NOT NULL,
    pincode         TEXT,
    phone           TEXT,
    email           TEXT,
    website         TEXT,
    operating_hours TEXT,
    is_24_7         INTEGER NOT NULL DEFAULT 0 CHECK (is_24_7 IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_providers_city   ON Providers(city);
CREATE INDEX IF NOT EXISTS idx_providers_state  ON Providers(state);
CREATE INDEX IF NOT EXISTS idx_providers_coords ON Providers(latitude, longitude);

-- ─── T3: Zones ──────────────────────────────────────────────────────────────
-- Disaster / allocation zones
CREATE TABLE IF NOT EXISTS Zones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_name   TEXT    NOT NULL UNIQUE,
    region      TEXT    NOT NULL DEFAULT '',
    state       TEXT    NOT NULL DEFAULT '',
    population  INTEGER NOT NULL DEFAULT 0 CHECK (population >= 0),
    area_sqkm   REAL    NOT NULL DEFAULT 0 CHECK (area_sqkm >= 0),
    risk_level  TEXT    NOT NULL DEFAULT 'Low'
                        CHECK (risk_level IN ('Low','Medium','High','Critical')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_zones_risk ON Zones(risk_level);

-- ─── T4: Requests ───────────────────────────────────────────────────────────
-- Resource requests from disaster zones
CREATE TABLE IF NOT EXISTS Requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id             INTEGER NOT NULL,
    resource_id         INTEGER NOT NULL,
    quantity_requested  REAL    NOT NULL CHECK (quantity_requested > 0),
    severity            REAL    NOT NULL DEFAULT 1.0 CHECK (severity > 0),
    population_affected INTEGER NOT NULL DEFAULT 0 CHECK (population_affected >= 0),
    urgency             REAL    NOT NULL DEFAULT 1.0 CHECK (urgency > 0),
    priority_score      REAL,
    status              TEXT    NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','allocated','fulfilled','rejected')),
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (zone_id)     REFERENCES Zones(id)     ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_requests_zone     ON Requests(zone_id);
CREATE INDEX IF NOT EXISTS idx_requests_resource ON Requests(resource_id);
CREATE INDEX IF NOT EXISTS idx_requests_status   ON Requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_priority ON Requests(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_requests_created  ON Requests(created_at);

-- ─── T5: Allocations ────────────────────────────────────────────────────────
-- Which provider fulfilled (part of) which request
CREATE TABLE IF NOT EXISTS Allocations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id          INTEGER NOT NULL,
    provider_id         INTEGER NOT NULL,
    resource_id         INTEGER NOT NULL,
    quantity_allocated  REAL    NOT NULL CHECK (quantity_allocated > 0),
    allocated_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (request_id)  REFERENCES Requests(id)  ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_allocs_request  ON Allocations(request_id);
CREATE INDEX IF NOT EXISTS idx_allocs_provider ON Allocations(provider_id);
CREATE INDEX IF NOT EXISTS idx_allocs_resource ON Allocations(resource_id);
CREATE INDEX IF NOT EXISTS idx_allocs_date     ON Allocations(allocated_at);

-- ─── T6: AllocationHistory ──────────────────────────────────────────────────
-- Detailed audit trail for every allocation transaction
CREATE TABLE IF NOT EXISTS AllocationHistory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL,
    provider_id     INTEGER NOT NULL,
    resource_id     INTEGER NOT NULL,
    qty_before      REAL    NOT NULL,
    qty_after       REAL    NOT NULL,
    qty_allocated   REAL    NOT NULL CHECK (qty_allocated > 0),
    action          TEXT    NOT NULL DEFAULT 'allocate'
                            CHECK (action IN ('allocate','restock','adjustment','rollback')),
    performed_by    TEXT    NOT NULL DEFAULT 'system',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (request_id)  REFERENCES Requests(id)  ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ah_request  ON AllocationHistory(request_id);
CREATE INDEX IF NOT EXISTS idx_ah_provider ON AllocationHistory(provider_id);
CREATE INDEX IF NOT EXISTS idx_ah_resource ON AllocationHistory(resource_id);
CREATE INDEX IF NOT EXISTS idx_ah_created  ON AllocationHistory(created_at);

-- ─── T7: AuditLog ───────────────────────────────────────────────────────────
-- Universal audit log: every write in the system is tracked here
CREATE TABLE IF NOT EXISTS AuditLog (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user            TEXT    NOT NULL DEFAULT 'system',
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    action_type     TEXT    NOT NULL CHECK (action_type IN (
                        'allocation','stock_update','risk_update',
                        'threshold_change','request_create','request_update',
                        'restock','alert','system','zone_update'
                    )),
    table_name      TEXT    NOT NULL,
    record_id       INTEGER,
    previous_value  TEXT,
    new_value       TEXT,
    details         TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_ts     ON AuditLog(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON AuditLog(action_type);
CREATE INDEX IF NOT EXISTS idx_audit_table  ON AuditLog(table_name);

-- ─── T8: StockLevels ────────────────────────────────────────────────────────
-- Current stock at each provider (center) — the live inventory
CREATE TABLE IF NOT EXISTS StockLevels (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id         INTEGER NOT NULL,
    resource_id         INTEGER NOT NULL,
    quantity            REAL    NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    low_stock_threshold REAL    NOT NULL DEFAULT 10 CHECK (low_stock_threshold >= 0),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE,
    UNIQUE(provider_id, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_sl_provider ON StockLevels(provider_id);
CREATE INDEX IF NOT EXISTS idx_sl_resource ON StockLevels(resource_id);
CREATE INDEX IF NOT EXISTS idx_sl_quantity ON StockLevels(quantity);

-- ─── T9: StockThresholds ────────────────────────────────────────────────────
-- Per-resource configurable warning/critical thresholds
CREATE TABLE IF NOT EXISTS StockThresholds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     INTEGER NOT NULL,
    warning_level   REAL    NOT NULL DEFAULT 20 CHECK (warning_level >= 0),
    critical_level  REAL    NOT NULL DEFAULT 5  CHECK (critical_level >= 0),
    auto_alert      INTEGER NOT NULL DEFAULT 1  CHECK (auto_alert IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE,
    UNIQUE(resource_id)
);

-- ─── T10: RiskScores ────────────────────────────────────────────────────────
-- Materialized risk analysis (updated by stored procedures + triggers)
-- Forecast module reads from this table directly
CREATE TABLE IF NOT EXISTS RiskScores (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id             INTEGER NOT NULL,
    provider_id             INTEGER NOT NULL,
    depletion_probability   REAL    NOT NULL DEFAULT 0 CHECK (depletion_probability BETWEEN 0 AND 1),
    average_consumption     REAL    NOT NULL DEFAULT 0 CHECK (average_consumption >= 0),
    risk_index              REAL    NOT NULL DEFAULT 0 CHECK (risk_index BETWEEN 0 AND 100),
    classification          TEXT    NOT NULL DEFAULT 'Low'
                                    CHECK (classification IN ('Low','Medium','High','Critical')),
    last_calculated         TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    UNIQUE(resource_id, provider_id)
);

CREATE INDEX IF NOT EXISTS idx_risk_resource ON RiskScores(resource_id);
CREATE INDEX IF NOT EXISTS idx_risk_provider ON RiskScores(provider_id);
CREATE INDEX IF NOT EXISTS idx_risk_class    ON RiskScores(classification);
CREATE INDEX IF NOT EXISTS idx_risk_index    ON RiskScores(risk_index DESC);

-- ─── T11: ResourceConsumptionRate ───────────────────────────────────────────
-- Consumption velocity tracking for depletion forecasting
CREATE TABLE IF NOT EXISTS ResourceConsumptionRate (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     INTEGER NOT NULL,
    provider_id     INTEGER NOT NULL,
    daily_rate      REAL    NOT NULL DEFAULT 0 CHECK (daily_rate >= 0),
    weekly_rate     REAL    NOT NULL DEFAULT 0 CHECK (weekly_rate >= 0),
    monthly_rate    REAL    NOT NULL DEFAULT 0 CHECK (monthly_rate >= 0),
    trend_direction TEXT    NOT NULL DEFAULT 'stable'
                            CHECK (trend_direction IN ('increasing','decreasing','stable')),
    last_calculated TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    UNIQUE(resource_id, provider_id)
);

CREATE INDEX IF NOT EXISTS idx_cr_resource ON ResourceConsumptionRate(resource_id);
CREATE INDEX IF NOT EXISTS idx_cr_provider ON ResourceConsumptionRate(provider_id);

-- ─── T12: ZoneSummary ───────────────────────────────────────────────────────
-- Pre-aggregated zone statistics (materialized by triggers and procedures)
CREATE TABLE IF NOT EXISTS ZoneSummary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id         INTEGER NOT NULL,
    zone_name       TEXT    NOT NULL UNIQUE,
    total_requests  INTEGER NOT NULL DEFAULT 0 CHECK (total_requests >= 0),
    total_allocated REAL    NOT NULL DEFAULT 0 CHECK (total_allocated >= 0),
    pending_requests INTEGER NOT NULL DEFAULT 0 CHECK (pending_requests >= 0),
    shortage_ratio  REAL    NOT NULL DEFAULT 0,
    avg_severity    REAL    NOT NULL DEFAULT 0,
    avg_urgency     REAL    NOT NULL DEFAULT 0,
    last_updated    TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (zone_id) REFERENCES Zones(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_zs_zone     ON ZoneSummary(zone_id);
CREATE INDEX IF NOT EXISTS idx_zs_shortage ON ZoneSummary(shortage_ratio DESC);


-- #############################################################################
-- SECTION 2 — SUPPORT TABLES (kept for AI/Search/UI compatibility)
-- #############################################################################

-- Service categories (used by AI NLP intent classifier)
CREATE TABLE IF NOT EXISTS ServiceCategory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    keywords    TEXT NOT NULL
);

-- Provider-to-category junction (used by search service)
CREATE TABLE IF NOT EXISTS ServicesOffered (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    details     TEXT,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES ServiceCategory(id) ON DELETE CASCADE,
    UNIQUE(provider_id, category_id)
);

CREATE INDEX IF NOT EXISTS idx_so_provider ON ServicesOffered(provider_id);
CREATE INDEX IF NOT EXISTS idx_so_category ON ServicesOffered(category_id);

-- Emergency contacts (used by results page)
CREATE TABLE IF NOT EXISTS EmergencyContact (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    number      TEXT NOT NULL,
    category_id INTEGER,
    scope       TEXT,
    region      TEXT,
    FOREIGN KEY (category_id) REFERENCES ServiceCategory(id) ON DELETE SET NULL
);

-- Stock change history (used by depletion forecast engine)
CREATE TABLE IF NOT EXISTS StockHistory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id     INTEGER NOT NULL,
    resource_id     INTEGER NOT NULL,
    quantity_before REAL    NOT NULL,
    quantity_after  REAL    NOT NULL,
    change_type     TEXT    NOT NULL CHECK (change_type IN ('allocation','restock','adjustment')),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    details         TEXT,
    FOREIGN KEY (provider_id) REFERENCES Providers(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES Resources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sh_provider ON StockHistory(provider_id);
CREATE INDEX IF NOT EXISTS idx_sh_resource ON StockHistory(resource_id);
CREATE INDEX IF NOT EXISTS idx_sh_created  ON StockHistory(created_at);

-- Anonymized user query log (search audit)
CREATE TABLE IF NOT EXISTS UserQuery (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text_anon   TEXT NOT NULL,
    category_detected TEXT NOT NULL,
    latitude          REAL,
    longitude         REAL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_uq_created ON UserQuery(created_at);

-- System log (backward-compat operational log)
CREATE TABLE IF NOT EXISTS SystemLog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   INTEGER,
    details     TEXT
);

CREATE INDEX IF NOT EXISTS idx_syslog_created ON SystemLog(created_at);
CREATE INDEX IF NOT EXISTS idx_syslog_action  ON SystemLog(action);


-- #############################################################################
-- SECTION 3 — BACKWARD-COMPATIBILITY VIEWS (AI modules use old table names)
-- #############################################################################

-- Old: ResourceType → New: Resources
CREATE VIEW IF NOT EXISTS ResourceType AS
SELECT id, name, unit FROM Resources;

-- Old: ServiceProvider → New: Providers
CREATE VIEW IF NOT EXISTS ServiceProvider AS
SELECT id, name, description, id AS location_id,
       phone, email, website, operating_hours, is_24_7
FROM Providers;

-- Old: Location → New: embedded in Providers
CREATE VIEW IF NOT EXISTS Location AS
SELECT id, latitude, longitude, address, city, state, pincode
FROM Providers;

-- Old: ResourceStock → New: StockLevels
CREATE VIEW IF NOT EXISTS ResourceStock AS
SELECT id, provider_id, resource_id AS resource_type_id,
       quantity, low_stock_threshold, updated_at
FROM StockLevels;

-- Old: ResourceRequest → New: Requests + Zones
CREATE VIEW IF NOT EXISTS ResourceRequest AS
SELECT r.id, z.zone_name, r.resource_id AS resource_type_id,
       r.quantity_requested, r.severity, r.population_affected,
       r.urgency, r.priority_score, r.status, r.created_at, r.updated_at
FROM Requests r
JOIN Zones z ON r.zone_id = z.id;

-- Old: Allocation → New: Allocations
CREATE VIEW IF NOT EXISTS Allocation AS
SELECT id, request_id, provider_id, resource_id AS resource_type_id,
       quantity_allocated, allocated_at
FROM Allocations;

-- Live stock summary view (used by Live Stock page)
CREATE VIEW IF NOT EXISTS v_center_stock_summary AS
SELECT
    sl.id           AS stock_id,
    p.id            AS provider_id,
    p.name          AS center_name,
    r.id            AS resource_type_id,
    r.name          AS resource_name,
    r.unit,
    sl.quantity,
    sl.low_stock_threshold,
    CASE WHEN sl.quantity < sl.low_stock_threshold THEN 1 ELSE 0 END AS is_low,
    sl.updated_at
FROM StockLevels sl
JOIN Providers p  ON sl.provider_id = p.id
JOIN Resources r  ON sl.resource_id = r.id;


-- #############################################################################
-- SECTION 4 — TRIGGERS (automated DBMS behaviors)
-- #############################################################################

-- ═══ TRIGGER 1: Prevent negative stock (data integrity enforcement) ═══
-- Safety rule: stock can NEVER go negative — enforced at database level
CREATE TRIGGER IF NOT EXISTS trg_prevent_negative_stock
BEFORE UPDATE ON StockLevels
FOR EACH ROW
WHEN NEW.quantity < 0
BEGIN
    SELECT RAISE(ABORT, 'CONSTRAINT VIOLATION: Stock quantity cannot be negative');
END;

-- ═══ TRIGGER 2: Auto-log stock changes into AuditLog ═══
-- Every stock quantity change is automatically recorded for audit trail
CREATE TRIGGER IF NOT EXISTS trg_stock_change_log
AFTER UPDATE ON StockLevels
FOR EACH ROW
WHEN OLD.quantity != NEW.quantity
BEGIN
    INSERT INTO AuditLog (user, action_type, table_name, record_id,
                          previous_value, new_value, details)
    VALUES (
        'system', 'stock_update', 'StockLevels', NEW.id,
        CAST(OLD.quantity AS TEXT), CAST(NEW.quantity AS TEXT),
        'Stock changed from ' || CAST(OLD.quantity AS TEXT) || ' to ' ||
        CAST(NEW.quantity AS TEXT) || ' for resource_id=' ||
        CAST(NEW.resource_id AS TEXT) || ' at provider_id=' ||
        CAST(NEW.provider_id AS TEXT)
    );
END;

-- ═══ TRIGGER 3: Low stock alert when quantity drops below threshold ═══
-- Auto-creates alert AuditLog entry when stock crosses threshold boundary
CREATE TRIGGER IF NOT EXISTS trg_low_stock_alert
AFTER UPDATE ON StockLevels
FOR EACH ROW
WHEN NEW.quantity < NEW.low_stock_threshold
 AND OLD.quantity >= OLD.low_stock_threshold
BEGIN
    INSERT INTO AuditLog (user, action_type, table_name, record_id,
                          previous_value, new_value, details)
    VALUES (
        'system', 'alert', 'StockLevels', NEW.id,
        CAST(OLD.quantity AS TEXT), CAST(NEW.quantity AS TEXT),
        'LOW STOCK ALERT: resource_id=' || CAST(NEW.resource_id AS TEXT) ||
        ' at provider_id=' || CAST(NEW.provider_id AS TEXT) ||
        ' dropped to ' || CAST(NEW.quantity AS TEXT) ||
        ' (threshold: ' || CAST(NEW.low_stock_threshold AS TEXT) || ')'
    );
END;

-- ═══ TRIGGER 4: Auto-update ZoneSummary aggregates after allocation ═══
-- Demonstrates: trigger-driven materialized aggregation
CREATE TRIGGER IF NOT EXISTS trg_zone_summary_update
AFTER INSERT ON Allocations
FOR EACH ROW
BEGIN
    INSERT OR REPLACE INTO ZoneSummary
        (zone_id, zone_name, total_requests, total_allocated,
         pending_requests, shortage_ratio, avg_severity, avg_urgency, last_updated)
    SELECT
        z.id,
        z.zone_name,
        COUNT(DISTINCT r2.id),
        COALESCE(SUM(a2.quantity_allocated), 0),
        COUNT(DISTINCT CASE WHEN r2.status = 'pending' THEN r2.id END),
        CASE
            WHEN COALESCE(SUM(r2.quantity_requested), 0) = 0 THEN 0
            ELSE ROUND(1.0 - (COALESCE(SUM(a2.quantity_allocated), 0) /
                        SUM(r2.quantity_requested)), 4)
        END,
        ROUND(AVG(r2.severity), 2),
        ROUND(AVG(r2.urgency), 2),
        datetime('now')
    FROM Requests req
    JOIN Zones z ON req.zone_id = z.id
    LEFT JOIN Requests r2 ON r2.zone_id = z.id
    LEFT JOIN Allocations a2 ON a2.request_id = r2.id
    WHERE req.id = NEW.request_id
    GROUP BY z.id, z.zone_name;
END;

-- ═══ TRIGGER 5: Auto-calculate RiskScore when stock drops below critical ═══
-- Demonstrates: trigger-driven risk materialization
CREATE TRIGGER IF NOT EXISTS trg_risk_on_low_stock
AFTER UPDATE ON StockLevels
FOR EACH ROW
WHEN NEW.quantity < COALESCE(
    (SELECT critical_level FROM StockThresholds WHERE resource_id = NEW.resource_id), 5
)
BEGIN
    INSERT OR REPLACE INTO RiskScores
        (resource_id, provider_id, depletion_probability, average_consumption,
         risk_index, classification, last_calculated)
    VALUES (
        NEW.resource_id,
        NEW.provider_id,
        -- Depletion probability: 0..1
        CASE
            WHEN NEW.quantity <= 0 THEN 1.0
            WHEN NEW.low_stock_threshold <= 0 THEN 0.5
            ELSE MIN(1.0, 1.0 - (NEW.quantity / (NEW.low_stock_threshold * 2.0)))
        END,
        -- Average consumption from StockHistory
        COALESCE(
            (SELECT AVG(ABS(quantity_before - quantity_after))
             FROM StockHistory
             WHERE provider_id = NEW.provider_id
               AND resource_id = NEW.resource_id
               AND change_type = 'allocation'), 0
        ),
        -- Risk index: 0..100
        CASE
            WHEN NEW.quantity <= 0 THEN 100
            WHEN NEW.low_stock_threshold <= 0 THEN 50
            ELSE MIN(100, CAST(
                ((1.0 - (NEW.quantity / (NEW.low_stock_threshold * 2.0))) * 100)
                AS INTEGER))
        END,
        -- Classification: Low/Medium/High/Critical
        CASE
            WHEN NEW.quantity <= 0 THEN 'Critical'
            WHEN NEW.quantity < COALESCE(
                (SELECT critical_level FROM StockThresholds
                 WHERE resource_id = NEW.resource_id), 5) THEN 'Critical'
            WHEN NEW.quantity < NEW.low_stock_threshold THEN 'High'
            WHEN NEW.quantity < NEW.low_stock_threshold * 1.5 THEN 'Medium'
            ELSE 'Low'
        END,
        datetime('now')
    );
END;


-- #############################################################################
-- SECTION 5 — ANALYTICAL SQL VIEWS
-- Uses: GROUP BY, HAVING, JOIN, Subqueries, Aggregations
-- #############################################################################

-- ═══ VIEW 1: High Risk Zones ═══
-- Zones where shortage_ratio > 0.3 (significant supply gaps)
CREATE VIEW IF NOT EXISTS v_high_risk_zones AS
SELECT
    z.zone_name,
    COUNT(DISTINCT r.id)                            AS total_requests,
    SUM(r.quantity_requested)                       AS total_demand,
    COALESCE(alloc_agg.total_allocated, 0)          AS total_supplied,
    ROUND(
        CASE WHEN SUM(r.quantity_requested) = 0 THEN 0
        ELSE 1.0 - (COALESCE(alloc_agg.total_allocated, 0) /
                     SUM(r.quantity_requested))
        END, 4
    )                                               AS shortage_ratio,
    ROUND(AVG(r.severity), 2)                       AS avg_severity,
    ROUND(AVG(r.urgency), 2)                        AS avg_urgency,
    COUNT(DISTINCT CASE WHEN r.status = 'pending' THEN r.id END)
                                                    AS pending_count
FROM Requests r
JOIN Zones z ON r.zone_id = z.id
LEFT JOIN (
    SELECT a.request_id, SUM(a.quantity_allocated) AS total_allocated
    FROM Allocations a GROUP BY a.request_id
) alloc_agg ON alloc_agg.request_id = r.id
GROUP BY z.zone_name
HAVING shortage_ratio > 0.3
ORDER BY shortage_ratio DESC;

-- ═══ VIEW 2: Fastest Depleting Resources ═══
-- Ranked by days until depletion (consumption rate ÷ stock)
CREATE VIEW IF NOT EXISTS v_fastest_depleting_resources AS
SELECT
    res.name                                        AS resource_name,
    res.unit,
    p.name                                          AS provider_name,
    sl.quantity                                     AS current_stock,
    sl.low_stock_threshold,
    COALESCE(cr.daily_rate, 0)                      AS daily_consumption,
    COALESCE(cr.weekly_rate, 0)                     AS weekly_consumption,
    CASE
        WHEN COALESCE(cr.daily_rate, 0) = 0 THEN 9999
        ELSE ROUND(sl.quantity / cr.daily_rate, 1)
    END                                             AS days_until_depletion,
    cr.trend_direction
FROM StockLevels sl
JOIN Resources res ON sl.resource_id = res.id
JOIN Providers p   ON sl.provider_id = p.id
LEFT JOIN ResourceConsumptionRate cr
    ON cr.resource_id = sl.resource_id AND cr.provider_id = sl.provider_id
WHERE sl.quantity > 0
ORDER BY days_until_depletion ASC;

-- ═══ VIEW 3: Provider Efficiency ═══
-- Allocation performance metrics per provider with subquery for city-level context
CREATE VIEW IF NOT EXISTS v_provider_efficiency AS
SELECT
    p.id                                            AS provider_id,
    p.name                                          AS provider_name,
    p.city,
    COUNT(DISTINCT a.id)                            AS total_allocations,
    COALESCE(SUM(a.quantity_allocated), 0)           AS total_qty_allocated,
    COALESCE(req_stats.total_requests_in_city, 0)   AS total_requests_in_city,
    CASE
        WHEN COALESCE(req_stats.total_requests_in_city, 0) = 0 THEN 0
        ELSE ROUND(
            CAST(COUNT(DISTINCT a.id) AS REAL) /
            req_stats.total_requests_in_city * 100, 2)
    END                                             AS fulfillment_rate_pct,
    ROUND(AVG(a.quantity_allocated), 2)              AS avg_allocation_size
FROM Providers p
LEFT JOIN Allocations a ON a.provider_id = p.id
LEFT JOIN (
    SELECT p2.city,
           COUNT(DISTINCT r.id) AS total_requests_in_city
    FROM Requests r
    JOIN Allocations a2 ON a2.request_id = r.id
    JOIN Providers p2   ON a2.provider_id = p2.id
    GROUP BY p2.city
) req_stats ON req_stats.city = p.city
GROUP BY p.id, p.name, p.city
ORDER BY fulfillment_rate_pct DESC;

-- ═══ VIEW 4: Allocation Performance ═══
-- Time-series allocation statistics (daily aggregate)
CREATE VIEW IF NOT EXISTS v_allocation_performance AS
SELECT
    date(a.allocated_at)                            AS allocation_date,
    COUNT(a.id)                                     AS allocation_count,
    SUM(a.quantity_allocated)                        AS total_qty,
    ROUND(AVG(a.quantity_allocated), 2)              AS avg_qty,
    COUNT(DISTINCT a.provider_id)                   AS providers_involved,
    COUNT(DISTINCT a.resource_id)                   AS resource_types_involved,
    COUNT(DISTINCT z.zone_name)                     AS zones_served
FROM Allocations a
JOIN Requests r ON a.request_id = r.id
JOIN Zones z ON r.zone_id = z.id
GROUP BY date(a.allocated_at)
ORDER BY allocation_date DESC;

-- ═══ VIEW 5: Zone Shortage Analysis ═══
-- Demand vs supply gap per zone + resource (uses correlated subquery)
CREATE VIEW IF NOT EXISTS v_zone_shortage_analysis AS
SELECT
    z.zone_name,
    res.name                                        AS resource_name,
    SUM(r.quantity_requested)                       AS total_demanded,
    COALESCE(
        (SELECT SUM(a.quantity_allocated)
         FROM Allocations a
         WHERE a.request_id IN (
             SELECT r2.id FROM Requests r2
             WHERE r2.zone_id = r.zone_id AND r2.resource_id = r.resource_id
         )
        ), 0
    )                                               AS total_supplied,
    SUM(r.quantity_requested) - COALESCE(
        (SELECT SUM(a.quantity_allocated)
         FROM Allocations a
         WHERE a.request_id IN (
             SELECT r2.id FROM Requests r2
             WHERE r2.zone_id = r.zone_id AND r2.resource_id = r.resource_id
         )
        ), 0
    )                                               AS supply_gap,
    ROUND(AVG(r.severity), 2)                       AS avg_severity,
    MAX(r.urgency)                                  AS max_urgency,
    SUM(r.population_affected)                      AS total_population_affected
FROM Requests r
JOIN Zones z ON r.zone_id = z.id
JOIN Resources res ON r.resource_id = res.id
GROUP BY z.zone_name, r.resource_id
HAVING supply_gap > 0
ORDER BY supply_gap DESC, avg_severity DESC;
