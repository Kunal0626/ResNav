-- ===========================================================================
-- 02_procedures.sql -- the decisions.
--
-- Triggers enforce invariants; procedures decide. Everything here needs at
-- least one of the three things a trigger cannot do: a transaction, a loop,
-- or a lock taken before the decision is made.
-- ===========================================================================

DROP PROCEDURE IF EXISTS sp_allocate_request;
DROP PROCEDURE IF EXISTS sp_allocate_open_requests;
DROP PROCEDURE IF EXISTS sp_cancel_request;
DROP PROCEDURE IF EXISTS sp_restock_center;

DELIMITER $$

-- ═══════════════════════════════════════════════════════════════════════════
-- sp_allocate_request -- fill one request, nearest centre first, atomically.
--
-- THE LOCKING STRATEGY, which is the point of this procedure:
--
-- Two sessions that lock the same rows in different orders deadlock. The fix
-- is not retry logic, it is to make the situation impossible. So this takes
-- every lock it will need UP FRONT, in one statement, in primary-key order:
--
--     SELECT ... WHERE resource_id = ? ORDER BY provider_id FOR UPDATE
--
-- InnoDB locks rows as it reads them, and ix_stocklevels_resource_provider
-- is (resource_id, provider_id), so that scan acquires locks in ascending
-- provider_id order -- the same order for every session, always. That index
-- exists for this as much as for the allocator's lookup.
--
-- Only once every lock is held does it rank candidates by distance and
-- allocate. That ordering matters:
--
--   * Locking in DISTANCE order would be a different order per request,
--     because distance depends on the requesting zone. Two requests from
--     different zones would lock the same two centres in opposite orders.
--     That is a deadlock, and Phase 6 demonstrates it deliberately.
--   * Reading the quantities AFTER taking the locks is what makes the
--     numbers trustworthy. An unlocked read followed by an allocation
--     against those stale numbers is precisely the oversell bug.
--
-- The cost is honest: it locks every centre holding that resource, not only
-- the ones it ends up drawing from. Two allocations of the SAME resource
-- therefore serialise. Two allocations of different resources do not. For a
-- relief system that is the right trade -- correctness over throughput on a
-- path that runs seconds apart, not microseconds.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE PROCEDURE sp_allocate_request(
    IN  p_request_id   BIGINT UNSIGNED,
    OUT p_allocated    DECIMAL(12,3),
    OUT p_legs         INT,
    OUT p_status       VARCHAR(16)
)
MODIFIES SQL DATA
BEGIN
    DECLARE v_resource_id  SMALLINT UNSIGNED;
    DECLARE v_zone_lat     DECIMAL(9,6);
    DECLARE v_zone_lon     DECIMAL(9,6);
    DECLARE v_requested    DECIMAL(12,3);
    DECLARE v_already      DECIMAL(12,3);
    DECLARE v_outstanding  DECIMAL(12,3);
    DECLARE v_req_status   VARCHAR(16);
    DECLARE v_provider_id  INT UNSIGNED;
    DECLARE v_available    DECIMAL(12,3);
    DECLARE v_take         DECIMAL(12,3);
    DECLARE v_done         INT DEFAULT 0;
    DECLARE v_lock_sink    INT;

    -- Pass 1: take the locks, in primary-key order. The fetched value is
    -- discarded; the point is the FOR UPDATE.
    DECLARE cur_lock CURSOR FOR
        SELECT provider_id
          FROM StockLevels
         WHERE resource_id = v_resource_id
         ORDER BY provider_id
           FOR UPDATE;

    -- Pass 2: now that every row is locked, rank by real distance and read
    -- quantities that cannot change underneath us.
    DECLARE cur_plan CURSOR FOR
        SELECT sl.provider_id, sl.quantity
          FROM StockLevels sl
          JOIN Providers p ON p.id = sl.provider_id
         WHERE sl.resource_id = v_resource_id
           AND sl.quantity > 0
         ORDER BY fn_haversine_km(v_zone_lat, v_zone_lon, p.latitude, p.longitude) ASC,
                  sl.quantity DESC,
                  sl.provider_id ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    -- Any failure undoes the whole allocation rather than leaving stock
    -- deducted with no matching Allocations row. RESIGNAL re-raises the
    -- original error with its SQLSTATE and message intact, so the caller
    -- still sees 'insufficient_stock' and not something this handler made up.
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_allocated = 0.000;
    SET p_legs = 0;

    START TRANSACTION;

    -- Lock the request itself, so two concurrent calls for the SAME request
    -- cannot both compute the same outstanding quantity.
    SELECT resource_id, quantity_requested, status
      INTO v_resource_id, v_requested, v_req_status
      FROM Requests
     WHERE id = p_request_id
       FOR UPDATE;

    IF v_resource_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'not_found: no such request';
    END IF;
    IF v_req_status IN ('fulfilled', 'rejected') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'request_closed: cannot allocate to a closed request';
    END IF;

    SELECT z.latitude, z.longitude INTO v_zone_lat, v_zone_lon
      FROM Requests r JOIN Zones z ON z.id = r.zone_id
     WHERE r.id = p_request_id;

    SELECT COALESCE(SUM(quantity_allocated), 0) INTO v_already
      FROM Allocations WHERE request_id = p_request_id AND status = 'active';

    SET v_outstanding = v_requested - v_already;

    IF v_outstanding > 0 THEN
        OPEN cur_lock;
        lock_loop: LOOP
            FETCH cur_lock INTO v_lock_sink;
            IF v_done = 1 THEN LEAVE lock_loop; END IF;
        END LOOP;
        CLOSE cur_lock;
        SET v_done = 0;

        OPEN cur_plan;
        plan_loop: LOOP
            FETCH cur_plan INTO v_provider_id, v_available;
            IF v_done = 1 OR v_outstanding <= 0 THEN LEAVE plan_loop; END IF;

            SET v_take = LEAST(v_available, v_outstanding);
            IF v_take > 0 THEN
                -- trg_allocations_bi_validate re-checks, trg_allocations_ai_apply
                -- moves the stock and advances the request status.
                INSERT INTO Allocations
                    (request_id, provider_id, resource_id, quantity_allocated)
                VALUES
                    (p_request_id, v_provider_id, v_resource_id, v_take);

                SET v_outstanding = v_outstanding - v_take;
                SET p_allocated   = p_allocated + v_take;
                SET p_legs        = p_legs + 1;
            END IF;
        END LOOP;
        CLOSE cur_plan;
    END IF;

    INSERT INTO AuditLog (actor, action_type, table_name, record_id, new_value, details)
    VALUES (COALESCE(@resnav_actor, CURRENT_USER()), 'allocation', 'Requests', p_request_id,
            CAST(p_allocated AS CHAR),
            CONCAT('allocated across ', p_legs, ' provider(s)'));

    SELECT status INTO p_status FROM Requests WHERE id = p_request_id;

    COMMIT;
END$$


-- ═══════════════════════════════════════════════════════════════════════════
-- sp_allocate_open_requests -- work the queue: highest priority, then oldest.
-- Each request is a separate transaction inside sp_allocate_request, so one
-- impossible request does not abandon the rest of the queue.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE PROCEDURE sp_allocate_open_requests(
    IN  p_limit     INT,
    OUT p_processed INT
)
MODIFIES SQL DATA
BEGIN
    DECLARE v_id        BIGINT UNSIGNED;
    DECLARE v_done      INT DEFAULT 0;
    DECLARE v_allocated DECIMAL(12,3);
    DECLARE v_legs      INT;
    DECLARE v_status    VARCHAR(16);

    DECLARE cur_queue CURSOR FOR
        SELECT id FROM Requests
         WHERE status IN ('pending', 'allocated')
         ORDER BY priority_score DESC, created_at ASC
         LIMIT 1000;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    SET p_processed = 0;
    OPEN cur_queue;
    queue_loop: LOOP
        FETCH cur_queue INTO v_id;
        IF v_done = 1 OR (p_limit > 0 AND p_processed >= p_limit) THEN
            LEAVE queue_loop;
        END IF;
        CALL sp_allocate_request(v_id, v_allocated, v_legs, v_status);
        SET p_processed = p_processed + 1;
    END LOOP;
    CLOSE cur_queue;
END$$


-- ═══════════════════════════════════════════════════════════════════════════
-- sp_cancel_request -- release every active allocation and return the stock.
-- A state change, not a DELETE: the allocations stay on record as 'released'
-- so the history of what was promised survives.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE PROCEDURE sp_cancel_request(
    IN  p_request_id BIGINT UNSIGNED,
    OUT p_released   DECIMAL(12,3),
    OUT p_legs       INT
)
MODIFIES SQL DATA
BEGIN
    DECLARE v_status VARCHAR(16);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT status INTO v_status FROM Requests WHERE id = p_request_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'not_found: no such request';
    END IF;
    IF v_status = 'rejected' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'already_cancelled: request is already rejected';
    END IF;

    SELECT COALESCE(SUM(quantity_allocated), 0), COUNT(*)
      INTO p_released, p_legs
      FROM Allocations WHERE request_id = p_request_id AND status = 'active';

    -- trg_allocations_au_release returns the stock per row and recomputes the
    -- request status. Ordering by provider keeps the lock order canonical
    -- here too, for the StockLevels updates those triggers perform.
    UPDATE Allocations
       SET status = 'released', released_at = CURRENT_TIMESTAMP(6)
     WHERE request_id = p_request_id AND status = 'active'
     ORDER BY provider_id, resource_id;

    UPDATE Requests SET status = 'rejected' WHERE id = p_request_id;

    INSERT INTO AuditLog (actor, action_type, table_name, record_id, previous_value, new_value, details)
    VALUES (COALESCE(@resnav_actor, CURRENT_USER()), 'release', 'Requests', p_request_id,
            v_status, 'rejected',
            CONCAT('released ', p_released, ' unit(s) across ', p_legs, ' allocation(s)'));

    COMMIT;
END$$


-- ═══════════════════════════════════════════════════════════════════════════
-- sp_restock_center -- add stock, creating the stock row if it is absent.
-- ═══════════════════════════════════════════════════════════════════════════
CREATE PROCEDURE sp_restock_center(
    IN  p_provider_id INT UNSIGNED,
    IN  p_resource_id SMALLINT UNSIGNED,
    IN  p_quantity    DECIMAL(12,3),
    OUT p_new_total   DECIMAL(12,3)
)
MODIFIES SQL DATA
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_quantity <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'bad_quantity: restock must be positive';
    END IF;

    START TRANSACTION;

    SET @resnav_change_type = 'restock';

    -- Upsert rather than check-then-insert, for the same reason the alert
    -- trigger does: the check-then-insert version is a race.
    INSERT INTO StockLevels (provider_id, resource_id, quantity)
    VALUES (p_provider_id, p_resource_id, p_quantity)
    ON DUPLICATE KEY UPDATE quantity = quantity + p_quantity;

    SET @resnav_change_type = NULL;

    SELECT quantity INTO p_new_total
      FROM StockLevels WHERE provider_id = p_provider_id AND resource_id = p_resource_id;

    INSERT INTO AuditLog (actor, action_type, table_name, record_id, new_value, details)
    VALUES (COALESCE(@resnav_actor, CURRENT_USER()), 'restock', 'StockLevels', NULL,
            CAST(p_new_total AS CHAR),
            CONCAT('provider ', p_provider_id, ' resource ', p_resource_id,
                   ' +', p_quantity));

    COMMIT;
END$$

DELIMITER ;
