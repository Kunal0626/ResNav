-- ===========================================================================
-- 01_triggers.sql -- the invariants.
--
-- The rule this project follows: TRIGGERS ENFORCE INVARIANTS, PROCEDURES MAKE
-- DECISIONS. Two MySQL facts force it:
--
--   1. A trigger cannot COMMIT or ROLLBACK -- it runs inside the transaction
--      of the statement that fired it. Anything that must succeed-or-undo as
--      a unit has to be a procedure.
--   2. A trigger cannot modify the table that fired it. No trigger on
--      StockLevels may write to StockLevels. This is why the low-stock alert
--      writes to StockAlerts rather than setting a flag on the stock row.
--
-- The chain runs in one direction only, and nested triggers do fire:
--     Allocations -> StockLevels -> {StockHistory, AuditLog, StockAlerts}
--
-- Where several triggers share a timing and event, FOLLOWS makes the order
-- explicit. MySQL permits multiple triggers per timing since 5.7.2, but
-- without FOLLOWS the firing order is creation order, which is invisible to
-- a reader of the file.
-- ===========================================================================

DROP TRIGGER IF EXISTS trg_stocklevels_bi_guard;
DROP TRIGGER IF EXISTS trg_stocklevels_bu_guard;
DROP TRIGGER IF EXISTS trg_stocklevels_au_history;
DROP TRIGGER IF EXISTS trg_stocklevels_au_audit;
DROP TRIGGER IF EXISTS trg_stocklevels_au_alert;
DROP TRIGGER IF EXISTS trg_allocations_bi_validate;
DROP TRIGGER IF EXISTS trg_allocations_ai_apply;
DROP TRIGGER IF EXISTS trg_allocations_au_release;
DROP TRIGGER IF EXISTS trg_requests_bi_closed_at;
DROP TRIGGER IF EXISTS trg_requests_bu_closed_at;

DELIMITER $$

-- ═══ R1: stock can never go negative ═══════════════════════════════════════
-- There is also CHECK (quantity >= 0) on the table. The trigger is not
-- redundant: it fires first and can say WHICH provider and resource, and by
-- how much, which a CHECK violation cannot. The CHECK is the backstop that
-- still holds if this trigger is ever dropped.

CREATE TRIGGER trg_stocklevels_bi_guard
BEFORE INSERT ON StockLevels
FOR EACH ROW
BEGIN
    IF NEW.quantity < 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'stock_negative: quantity cannot be negative';
    END IF;
END$$

CREATE TRIGGER trg_stocklevels_bu_guard
BEFORE UPDATE ON StockLevels
FOR EACH ROW
BEGIN
    -- MESSAGE_TEXT takes a SIMPLE VALUE -- a literal or a variable -- not an
    -- expression, so CONCAT() has to be assigned first. Writing
    -- `SET MESSAGE_TEXT = CONCAT(...)` fails with a bare syntax error that
    -- points at the parenthesis and explains nothing.
    DECLARE v_msg VARCHAR(255);
    IF NEW.quantity < 0 THEN
        SET v_msg = CONCAT(
            'stock_negative: provider ', NEW.provider_id,
            ' resource ', NEW.resource_id,
            ' would fall to ', NEW.quantity);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
    END IF;
END$$

-- ═══ R6: every stock movement is recorded ══════════════════════════════════
-- Writing this here rather than in the procedures is the whole point: a
-- caller that could skip the audit is not an audit. A hand-typed UPDATE in
-- the mysql client is recorded exactly like an allocation.
--
-- @resnav_change_type and @resnav_change_details let a procedure say WHY the
-- stock moved. Without them the direction of travel is the best guess
-- available, which is still better than nothing.

CREATE TRIGGER trg_stocklevels_au_history
AFTER UPDATE ON StockLevels
FOR EACH ROW
BEGIN
    IF NEW.quantity <> OLD.quantity THEN
        INSERT INTO StockHistory
            (provider_id, resource_id, quantity_before, quantity_after,
             change_type, details)
        VALUES
            (NEW.provider_id, NEW.resource_id, OLD.quantity, NEW.quantity,
             COALESCE(@resnav_change_type,
                      IF(NEW.quantity < OLD.quantity, 'allocation', 'restock')),
             @resnav_change_details);
    END IF;
END$$

CREATE TRIGGER trg_stocklevels_au_audit
AFTER UPDATE ON StockLevels
FOR EACH ROW FOLLOWS trg_stocklevels_au_history
BEGIN
    IF NEW.quantity <> OLD.quantity THEN
        INSERT INTO AuditLog
            (actor, action_type, table_name, record_id,
             previous_value, new_value, details)
        VALUES
            (COALESCE(@resnav_actor, CURRENT_USER()),
             'stock_update', 'StockLevels', NEW.id,
             CAST(OLD.quantity AS CHAR), CAST(NEW.quantity AS CHAR),
             CONCAT('provider ', NEW.provider_id, ' resource ', NEW.resource_id));
    END IF;
END$$

-- ═══ R5: at most one OPEN alert per (provider, resource) ═══════════════════
-- The obvious implementation is "if no open alert exists, insert one". That
-- is a race: two sessions can both find none, both insert, and the second
-- hits uq_stockalerts_one_open -- raising an error INSIDE a trigger, which
-- fails the UPDATE that fired it, which rolls back a perfectly valid
-- allocation. A monitoring feature able to break the thing it monitors.
--
-- So this does not check. ON DUPLICATE KEY UPDATE makes the insert a no-op
-- when an open alert already exists: one atomic statement, no window to lose,
-- no error to handle. The unique index guarantees the invariant and the
-- upsert makes hitting it harmless.

CREATE TRIGGER trg_stocklevels_au_alert
AFTER UPDATE ON StockLevels
FOR EACH ROW FOLLOWS trg_stocklevels_au_audit
BEGIN
    IF NEW.quantity < NEW.low_stock_threshold THEN
        INSERT INTO StockAlerts
            (provider_id, resource_id, quantity_at_alert, threshold_at_alert, status)
        VALUES
            (NEW.provider_id, NEW.resource_id, NEW.quantity, NEW.low_stock_threshold, 'open')
        ON DUPLICATE KEY UPDATE
            -- Deliberate no-op. The open alert already exists and keeps its
            -- original raised_at, because what matters is when the shortage
            -- STARTED, not when it was last observed.
            id = id;
    ELSEIF NEW.quantity >= NEW.low_stock_threshold THEN
        -- Recovered. Resolving clears the generated columns to NULL, which
        -- releases the unique slot for the next shortage.
        UPDATE StockAlerts
           SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP(6)
         WHERE provider_id = NEW.provider_id
           AND resource_id = NEW.resource_id
           AND status = 'open';
    END IF;
END$$

-- ═══ R3: an allocation cannot exceed stock, or what is outstanding ═════════
-- Advisory, not the guarantee. Under concurrency two sessions can both pass
-- this check before either writes -- which is exactly the race Phase 6
-- demonstrates. The real guarantees are sp_allocate_request's ordered
-- SELECT ... FOR UPDATE, and CHECK (quantity >= 0) underneath everything.
-- What this buys is a clear error instead of a constraint violation.

CREATE TRIGGER trg_allocations_bi_validate
BEFORE INSERT ON Allocations
FOR EACH ROW
BEGIN
    DECLARE v_available   DECIMAL(12,3);
    DECLARE v_requested   DECIMAL(12,3);
    DECLARE v_allocated   DECIMAL(12,3);
    DECLARE v_status      VARCHAR(16);

    SELECT quantity INTO v_available
      FROM StockLevels
     WHERE provider_id = NEW.provider_id AND resource_id = NEW.resource_id;

    IF v_available IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'no_stock_row: that provider holds no stock record for this resource';
    END IF;

    IF v_available < NEW.quantity_allocated THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'insufficient_stock: allocation exceeds stock on hand';
    END IF;

    SELECT quantity_requested, status INTO v_requested, v_status
      FROM Requests WHERE id = NEW.request_id;

    IF v_status IN ('fulfilled', 'rejected') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'request_closed: cannot allocate to a closed request';
    END IF;

    SELECT COALESCE(SUM(quantity_allocated), 0) INTO v_allocated
      FROM Allocations
     WHERE request_id = NEW.request_id AND status = 'active';

    IF v_allocated + NEW.quantity_allocated > v_requested THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'over_allocation: allocation exceeds the outstanding quantity';
    END IF;
END$$

-- ═══ R4 + inventory consistency ════════════════════════════════════════════
-- One write to Allocations moves the stock AND advances the request. Keeping
-- both beside the write that causes them is the only way they cannot be
-- forgotten by some future caller.

CREATE TRIGGER trg_allocations_ai_apply
AFTER INSERT ON Allocations
FOR EACH ROW
BEGIN
    DECLARE v_requested DECIMAL(12,3);
    DECLARE v_allocated DECIMAL(12,3);

    -- Fires trg_stocklevels_bu_guard, then the three AFTER UPDATE triggers.
    UPDATE StockLevels
       SET quantity = quantity - NEW.quantity_allocated
     WHERE provider_id = NEW.provider_id AND resource_id = NEW.resource_id;

    SELECT quantity_requested INTO v_requested FROM Requests WHERE id = NEW.request_id;
    SELECT COALESCE(SUM(quantity_allocated), 0) INTO v_allocated
      FROM Allocations WHERE request_id = NEW.request_id AND status = 'active';

    UPDATE Requests
       SET status = IF(v_allocated >= v_requested, 'fulfilled', 'allocated')
     WHERE id = NEW.request_id;
END$$

-- ═══ R8: releasing an allocation returns the stock ═════════════════════════
-- Cancelling is a state change, not a DELETE: "we promised this and then took
-- it back" is information an audited relief operation will be asked for.

CREATE TRIGGER trg_allocations_au_release
AFTER UPDATE ON Allocations
FOR EACH ROW
BEGIN
    DECLARE v_requested DECIMAL(12,3);
    DECLARE v_allocated DECIMAL(12,3);

    IF OLD.status = 'active' AND NEW.status = 'released' THEN
        SET @resnav_change_type = 'release';
        UPDATE StockLevels
           SET quantity = quantity + OLD.quantity_allocated
         WHERE provider_id = OLD.provider_id AND resource_id = OLD.resource_id;
        SET @resnav_change_type = NULL;

        SELECT quantity_requested INTO v_requested FROM Requests WHERE id = OLD.request_id;
        SELECT COALESCE(SUM(quantity_allocated), 0) INTO v_allocated
          FROM Allocations WHERE request_id = OLD.request_id AND status = 'active';

        -- Back to 'pending' when nothing is left allocated, so a released
        -- request re-enters the queue rather than sitting in a dead state.
        UPDATE Requests
           SET status = CASE
                          WHEN v_allocated <= 0           THEN 'pending'
                          WHEN v_allocated >= v_requested THEN 'fulfilled'
                          ELSE 'allocated'
                        END
         WHERE id = OLD.request_id AND status <> 'rejected';
    END IF;
END$$

-- ═══ closed_at always agrees with status ═══════════════════════════════════
-- ck_requests_closed_at enforces the agreement; these maintain it, so no
-- caller has to know the rule. The existing application sets only `status`
-- and keeps working unchanged.

CREATE TRIGGER trg_requests_bi_closed_at
BEFORE INSERT ON Requests
FOR EACH ROW
BEGIN
    IF NEW.status IN ('fulfilled', 'rejected') THEN
        SET NEW.closed_at = COALESCE(NEW.closed_at, CURRENT_TIMESTAMP(6));
    ELSE
        SET NEW.closed_at = NULL;
    END IF;
END$$

CREATE TRIGGER trg_requests_bu_closed_at
BEFORE UPDATE ON Requests
FOR EACH ROW
BEGIN
    IF NEW.status IN ('fulfilled', 'rejected') THEN
        SET NEW.closed_at = COALESCE(NEW.closed_at, CURRENT_TIMESTAMP(6));
    ELSE
        SET NEW.closed_at = NULL;
    END IF;
END$$

DELIMITER ;
