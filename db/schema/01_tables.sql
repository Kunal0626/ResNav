-- ===========================================================================
-- 01_tables.sql -- the merged schema.
--
-- Reasoning lives in docs/DESIGN.md; the old->new decisions and the evidence
-- behind them are in docs/MAPPING.md; the normal-form argument is in
-- docs/NORMALIZATION.md. This file is the implementation only.
--
-- Conventions:
--   * Surrogate integer primary key, plus UNIQUE on the real-world key. The
--     UNIQUE constraint is what actually keeps data honest and is what makes
--     the BCNF argument work.
--   * ON DELETE RESTRICT by default. Relief history must not evaporate
--     because somebody tidied a lookup table. CASCADE only where the child
--     has no existence of its own.
--   * Quantities DECIMAL(12,3), never FLOAT: stock arithmetic that drifts is
--     a correctness bug, and Phase 5's hand-checked seed needs exact equality.
--   * Timestamps DATETIME(6): microseconds, so Phase 6 can order two events
--     inside the same second.
--   * Idempotent: every object is dropped before it is created, so applying
--     this file twice is not an error.
-- ===========================================================================

-- Dropped in reverse dependency order so RESTRICT never blocks the teardown.
DROP TABLE IF EXISTS StockAlerts;
DROP TABLE IF EXISTS StockHistory;
DROP TABLE IF EXISTS Allocations;
DROP TABLE IF EXISTS Requests;
DROP TABLE IF EXISTS RiskScores;
DROP TABLE IF EXISTS ResourceConsumptionRate;
DROP TABLE IF EXISTS ZoneSummary;
DROP TABLE IF EXISTS StockLevels;
DROP TABLE IF EXISTS StockThresholds;
DROP TABLE IF EXISTS ServicesOffered;
DROP TABLE IF EXISTS EmergencyContact;
DROP TABLE IF EXISTS ServiceCategory;
DROP TABLE IF EXISTS Zones;
DROP TABLE IF EXISTS Providers;
DROP TABLE IF EXISTS Resources;
DROP TABLE IF EXISTS AuditLog;
DROP TABLE IF EXISTS UserQuery;


-- ─── Resources ──────────────────────────────────────────────────────────────
CREATE TABLE Resources (
    id          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(120)      NOT NULL,
    -- ENUM rather than a lookup table: the set is small, fixed, and a new
    -- unit is honestly a schema change. docs/MAPPING.md argues the trade-off.
    unit        ENUM('units','kg','litres','beds','packets','doses')
                                  NOT NULL DEFAULT 'units',
    category    VARCHAR(60)       NOT NULL DEFAULT 'general',
    created_at  DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_resources_name (name),
    KEY ix_resources_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Providers (relief centres) ─────────────────────────────────────────────
CREATE TABLE Providers (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name            VARCHAR(160) NOT NULL,
    description     VARCHAR(500) NOT NULL DEFAULT '',
    -- DECIMAL, not DOUBLE. Binary floating point cannot hold most decimal
    -- coordinates exactly, so `latitude = 13.082680` can be false for a row
    -- inserted with that literal. Six places is ~11 cm.
    latitude        DECIMAL(9,6) NOT NULL,
    longitude       DECIMAL(9,6) NOT NULL,
    address         VARCHAR(255) NULL,
    city            VARCHAR(80)  NOT NULL,
    state           VARCHAR(80)  NOT NULL,
    -- NULL-able, which is exactly why pincode -> city, state is NOT
    -- decomposed out. See docs/NORMALIZATION.md section 3d.
    pincode         VARCHAR(12)  NULL,
    phone           VARCHAR(32)  NULL,
    email           VARCHAR(160) NULL,
    website         VARCHAR(255) NULL,
    operating_hours VARCHAR(60)  NULL,
    is_24_7         TINYINT(1)   NOT NULL DEFAULT 0,
    created_at      DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_providers_name (name),
    KEY ix_providers_city (city),
    KEY ix_providers_state (state),
    KEY ix_providers_coords (latitude, longitude),
    CONSTRAINT ck_providers_latitude  CHECK (latitude  BETWEEN  -90 AND  90),
    CONSTRAINT ck_providers_longitude CHECK (longitude BETWEEN -180 AND 180),
    CONSTRAINT ck_providers_is_24_7   CHECK (is_24_7 IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Zones (disaster-affected areas) ────────────────────────────────────────
CREATE TABLE Zones (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    zone_name   VARCHAR(120) NOT NULL,
    region      VARCHAR(80)  NOT NULL DEFAULT '',
    state       VARCHAR(80)  NOT NULL DEFAULT '',
    population  INT UNSIGNED NOT NULL DEFAULT 0,
    area_sqkm   DECIMAL(10,2) NOT NULL DEFAULT 0,
    risk_level  ENUM('Low','Medium','High','Critical') NOT NULL DEFAULT 'Low',
    -- NEW in the merge. Without these, allocation ranked suppliers by
    -- same-state-or-not: a boolean standing in for distance. See
    -- docs/MAPPING.md finding 3.
    latitude    DECIMAL(9,6) NOT NULL,
    longitude   DECIMAL(9,6) NOT NULL,
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_zones_name (zone_name),
    KEY ix_zones_risk (risk_level),
    CONSTRAINT ck_zones_latitude  CHECK (latitude  BETWEEN  -90 AND  90),
    CONSTRAINT ck_zones_longitude CHECK (longitude BETWEEN -180 AND 180),
    CONSTRAINT ck_zones_area      CHECK (area_sqkm >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── StockThresholds (per-resource warning levels) ──────────────────────────
CREATE TABLE StockThresholds (
    resource_id    SMALLINT UNSIGNED NOT NULL,
    warning_level  DECIMAL(12,3) NOT NULL DEFAULT 20,
    critical_level DECIMAL(12,3) NOT NULL DEFAULT 5,
    auto_alert     TINYINT(1)    NOT NULL DEFAULT 1,
    created_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                 ON UPDATE CURRENT_TIMESTAMP(6),
    -- resource_id IS the key. ResNav carried a surrogate id plus
    -- UNIQUE(resource_id), which is two candidate keys for one fact.
    PRIMARY KEY (resource_id),
    CONSTRAINT fk_thresholds_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_thresholds_warning  CHECK (warning_level  >= 0),
    CONSTRAINT ck_thresholds_critical CHECK (critical_level >= 0),
    CONSTRAINT ck_thresholds_order    CHECK (critical_level <= warning_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── StockLevels (live inventory) ───────────────────────────────────────────
CREATE TABLE StockLevels (
    -- The surrogate stays because /api/stock returns it and the frontend uses
    -- it as a React key. It is NOT the primary key: (provider_id, resource_id)
    -- is the fact, and making it the clustered key is what the allocator
    -- locks against. AUTO_INCREMENT only requires the column to be first in
    -- SOME index, which the UNIQUE below satisfies.
    id                  INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    provider_id         INT UNSIGNED      NOT NULL,
    resource_id         SMALLINT UNSIGNED NOT NULL,
    quantity            DECIMAL(12,3)     NOT NULL DEFAULT 0,
    low_stock_threshold DECIMAL(12,3)     NOT NULL DEFAULT 10,
    updated_at          DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                          ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (provider_id, resource_id),
    UNIQUE KEY uq_stocklevels_id (id),
    -- The reverse of the primary key, and not redundant with it: a composite
    -- index only answers lookups that fix a leftmost prefix. The PK answers
    -- "what does provider 4 hold"; this answers "who holds resource 12", which
    -- is the allocator's question on every single run. docs/DESIGN.md 8.2.
    KEY ix_stocklevels_resource_provider (resource_id, provider_id),
    KEY ix_stocklevels_quantity (quantity),
    CONSTRAINT fk_stocklevels_provider FOREIGN KEY (provider_id)
        REFERENCES Providers (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_stocklevels_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- R1 as a constraint. The trigger rejects it earlier with a better
    -- message; this is the backstop that holds even if the trigger is dropped.
    CONSTRAINT ck_stocklevels_quantity  CHECK (quantity >= 0),
    CONSTRAINT ck_stocklevels_threshold CHECK (low_stock_threshold >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Requests ───────────────────────────────────────────────────────────────
CREATE TABLE Requests (
    id                  BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    zone_id             INT UNSIGNED      NOT NULL,
    resource_id         SMALLINT UNSIGNED NOT NULL,
    quantity_requested  DECIMAL(12,3)     NOT NULL,
    -- Range matches what the API already validates. ResNav's schema allowed
    -- anything > 0, so the database was weaker than the application -- a gap
    -- that lets a direct INSERT create a row the app could never produce.
    severity            DECIMAL(4,2)      NOT NULL DEFAULT 1.0,
    urgency             DECIMAL(4,2)      NOT NULL DEFAULT 1.0,
    population_affected INT UNSIGNED      NOT NULL DEFAULT 0,
    priority_score      DECIMAL(16,4)     NULL,
    status              ENUM('pending','allocated','fulfilled','rejected')
                                          NOT NULL DEFAULT 'pending',
    created_at          DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at          DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                          ON UPDATE CURRENT_TIMESTAMP(6),
    closed_at           DATETIME(6)       NULL,
    PRIMARY KEY (id),
    KEY ix_requests_zone (zone_id),
    KEY ix_requests_resource (resource_id),
    -- Serves allocate-the-queue: highest priority first, oldest first.
    KEY ix_requests_queue (status, priority_score DESC, created_at),
    CONSTRAINT fk_requests_zone FOREIGN KEY (zone_id)
        REFERENCES Zones (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_requests_quantity CHECK (quantity_requested > 0),
    CONSTRAINT ck_requests_severity CHECK (severity BETWEEN 0.1 AND 3.0),
    CONSTRAINT ck_requests_urgency  CHECK (urgency  BETWEEN 0.1 AND 3.0),
    -- A closed request has a closing time and an open one does not. Both
    -- sides evaluate to 0 or 1, so this is an equality of two booleans.
    -- trg_requests_* maintain closed_at so the application never has to.
    CONSTRAINT ck_requests_closed_at CHECK (
        (status IN ('fulfilled','rejected')) = (closed_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Allocations ────────────────────────────────────────────────────────────
CREATE TABLE Allocations (
    id                 BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    request_id         BIGINT UNSIGNED   NOT NULL,
    provider_id        INT UNSIGNED      NOT NULL,
    resource_id        SMALLINT UNSIGNED NOT NULL,
    quantity_allocated DECIMAL(12,3)     NOT NULL,
    -- Cancelling releases rather than deletes: "we promised this and then
    -- took it back" is information an audited relief operation will be asked
    -- for. The cost is that every query about current commitments must filter
    -- status = 'active', which is why the views do it centrally.
    status             ENUM('active','released') NOT NULL DEFAULT 'active',
    allocated_at       DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    released_at        DATETIME(6)       NULL,
    PRIMARY KEY (id),
    KEY ix_allocations_request (request_id, status),
    KEY ix_allocations_provider (provider_id, allocated_at),
    KEY ix_allocations_resource (resource_id),
    -- RESTRICT, not CASCADE: an allocation records that stock moved, and must
    -- outlive someone tidying up. Combined with the CASCADE-free Requests FK
    -- this means a request with allocations cannot be deleted at all, which
    -- is why sp_cancel_request exists.
    CONSTRAINT fk_allocations_request FOREIGN KEY (request_id)
        REFERENCES Requests (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_allocations_provider FOREIGN KEY (provider_id)
        REFERENCES Providers (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_allocations_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_allocations_quantity CHECK (quantity_allocated > 0),
    CONSTRAINT ck_allocations_released CHECK (
        (status = 'released') = (released_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── StockHistory (what the forecast engine actually reads) ─────────────────
CREATE TABLE StockHistory (
    id              BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    provider_id     INT UNSIGNED      NOT NULL,
    resource_id     SMALLINT UNSIGNED NOT NULL,
    quantity_before DECIMAL(12,3)     NOT NULL,
    quantity_after  DECIMAL(12,3)     NOT NULL,
    change_type     ENUM('allocation','restock','adjustment','release') NOT NULL,
    details         VARCHAR(255)      NULL,
    created_at      DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    -- Covering order for the forecast query: one provider+resource series,
    -- in time order.
    KEY ix_stockhistory_series (provider_id, resource_id, created_at),
    KEY ix_stockhistory_created (created_at)
    -- No foreign keys. History must survive the deletion of what it
    -- describes; see docs/DESIGN.md 6.3.
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── StockAlerts ────────────────────────────────────────────────────────────
CREATE TABLE StockAlerts (
    id                 BIGINT UNSIGNED   NOT NULL AUTO_INCREMENT,
    provider_id        INT UNSIGNED      NOT NULL,
    resource_id        SMALLINT UNSIGNED NOT NULL,
    quantity_at_alert  DECIMAL(12,3)     NOT NULL,
    threshold_at_alert DECIMAL(12,3)     NOT NULL,
    status             ENUM('open','resolved') NOT NULL DEFAULT 'open',
    raised_at          DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    resolved_at        DATETIME(6)       NULL,
    -- MySQL has no partial indexes, so "at most one OPEN alert per
    -- (provider, resource)" cannot be written as
    --     UNIQUE (provider_id, resource_id) WHERE status = 'open'
    -- the way PostgreSQL would. But a multi-column UNIQUE index ignores any
    -- row where an indexed column is NULL -- so two generated columns that go
    -- NULL the moment an alert is resolved give exactly that behaviour: open
    -- rows held unique, resolved rows free to repeat.
    open_provider_id   INT UNSIGNED      GENERATED ALWAYS AS
                           (IF(status = 'open', provider_id, NULL)) STORED,
    open_resource_id   SMALLINT UNSIGNED GENERATED ALWAYS AS
                           (IF(status = 'open', resource_id, NULL)) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uq_stockalerts_one_open (open_provider_id, open_resource_id),
    KEY ix_stockalerts_status (status, raised_at),
    -- ON UPDATE RESTRICT, not CASCADE, and not by preference: MySQL forbids
    -- CASCADE / SET NULL / SET DEFAULT on a foreign key over the BASE COLUMN
    -- of a stored generated column, and open_provider_id / open_resource_id
    -- are generated from exactly these two. Attempting CASCADE fails with
    -- "ERROR 1215 (HY000): Cannot add foreign key constraint", which names
    -- neither the column nor the reason. Harmless here: both parents are
    -- surrogate keys that are never updated.
    CONSTRAINT fk_stockalerts_stock FOREIGN KEY (provider_id, resource_id)
        REFERENCES StockLevels (provider_id, resource_id)
        ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT ck_stockalerts_resolved CHECK (
        (status = 'resolved') = (resolved_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── AuditLog (absorbs ResNav's SystemLog) ──────────────────────────────────
CREATE TABLE AuditLog (
    id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor          VARCHAR(128)    NOT NULL DEFAULT 'system',
    action_type    ENUM('allocation','release','stock_update','risk_update',
                        'threshold_change','request_create','request_update',
                        'restock','alert','navigation','system','zone_update')
                                   NOT NULL,
    table_name     VARCHAR(64)     NOT NULL,
    record_id      BIGINT UNSIGNED NULL,
    previous_value VARCHAR(255)    NULL,
    new_value      VARCHAR(255)    NULL,
    details        VARCHAR(500)    NULL,
    changed_at     DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_auditlog_changed (changed_at),
    KEY ix_auditlog_action (action_type, changed_at),
    KEY ix_auditlog_record (table_name, record_id)
    -- No foreign keys, deliberately. See docs/DESIGN.md 6.3.
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Search support ─────────────────────────────────────────────────────────
CREATE TABLE ServiceCategory (
    id          TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name        VARCHAR(60)      NOT NULL,
    description VARCHAR(255)     NULL,
    keywords    VARCHAR(500)     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_servicecategory_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ServicesOffered (
    provider_id INT UNSIGNED     NOT NULL,
    category_id TINYINT UNSIGNED NOT NULL,
    details     VARCHAR(255)     NULL,
    PRIMARY KEY (provider_id, category_id),
    KEY ix_servicesoffered_category (category_id),
    -- CASCADE here, and only here: a junction row has no meaning without the
    -- provider it joins.
    CONSTRAINT fk_servicesoffered_provider FOREIGN KEY (provider_id)
        REFERENCES Providers (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_servicesoffered_category FOREIGN KEY (category_id)
        REFERENCES ServiceCategory (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE EmergencyContact (
    id          INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    name        VARCHAR(120)     NOT NULL,
    number      VARCHAR(32)      NOT NULL,
    category_id TINYINT UNSIGNED NULL,
    scope       VARCHAR(40)      NULL,
    region      VARCHAR(80)      NULL,
    PRIMARY KEY (id),
    KEY ix_emergencycontact_category (category_id),
    CONSTRAINT fk_emergencycontact_category FOREIGN KEY (category_id)
        REFERENCES ServiceCategory (id) ON DELETE SET NULL ON UPDATE CASCADE
    -- This table is 3NF but not BCNF: number -> name, and number is not a
    -- superkey. Kept because the BCNF decomposition is lossless but NOT
    -- dependency-preserving. docs/NORMALIZATION.md section 4.
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Materialised aggregates, maintained by triggers ────────────────────────
-- On probation: these are kept only if Phase 4 makes the application read
-- them instead of recomputing in Python. docs/MAPPING.md finding 2.

CREATE TABLE RiskScores (
    resource_id           SMALLINT UNSIGNED NOT NULL,
    provider_id           INT UNSIGNED      NOT NULL,
    depletion_probability DECIMAL(5,4)      NOT NULL DEFAULT 0,
    average_consumption   DECIMAL(12,3)     NOT NULL DEFAULT 0,
    risk_index            DECIMAL(6,2)      NOT NULL DEFAULT 0,
    classification        ENUM('Low','Medium','High','Critical') NOT NULL DEFAULT 'Low',
    last_calculated       DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (resource_id, provider_id),
    KEY ix_riskscores_index (risk_index DESC),
    KEY ix_riskscores_class (classification),
    CONSTRAINT fk_riskscores_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_riskscores_provider FOREIGN KEY (provider_id)
        REFERENCES Providers (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_riskscores_probability CHECK (depletion_probability BETWEEN 0 AND 1),
    CONSTRAINT ck_riskscores_index       CHECK (risk_index BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ResourceConsumptionRate (
    resource_id     SMALLINT UNSIGNED NOT NULL,
    provider_id     INT UNSIGNED      NOT NULL,
    daily_rate      DECIMAL(12,3)     NOT NULL DEFAULT 0,
    weekly_rate     DECIMAL(12,3)     NOT NULL DEFAULT 0,
    monthly_rate    DECIMAL(12,3)     NOT NULL DEFAULT 0,
    trend_direction ENUM('increasing','decreasing','stable') NOT NULL DEFAULT 'stable',
    last_calculated DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (resource_id, provider_id),
    CONSTRAINT fk_consumption_resource FOREIGN KEY (resource_id)
        REFERENCES Resources (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_consumption_provider FOREIGN KEY (provider_id)
        REFERENCES Providers (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_consumption_daily CHECK (daily_rate >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ZoneSummary (
    zone_id          INT UNSIGNED  NOT NULL,
    total_requests   INT UNSIGNED  NOT NULL DEFAULT 0,
    total_allocated  DECIMAL(14,3) NOT NULL DEFAULT 0,
    pending_requests INT UNSIGNED  NOT NULL DEFAULT 0,
    shortage_ratio   DECIMAL(6,4)  NOT NULL DEFAULT 0,
    avg_severity     DECIMAL(4,2)  NOT NULL DEFAULT 0,
    avg_urgency      DECIMAL(4,2)  NOT NULL DEFAULT 0,
    last_updated     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (zone_id),
    KEY ix_zonesummary_shortage (shortage_ratio DESC),
    CONSTRAINT fk_zonesummary_zone FOREIGN KEY (zone_id)
        REFERENCES Zones (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT ck_zonesummary_shortage CHECK (shortage_ratio BETWEEN 0 AND 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;


-- ─── Anonymised search log ──────────────────────────────────────────────────
CREATE TABLE UserQuery (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    query_text_anon   VARCHAR(500)    NOT NULL,
    category_detected VARCHAR(60)     NOT NULL,
    latitude          DECIMAL(9,6)    NULL,
    longitude         DECIMAL(9,6)    NULL,
    created_at        DATETIME(6)     NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_userquery_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
