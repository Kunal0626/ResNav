-- The happy path, with every number checkable by hand.
-- Centre 3 holds 100 Blankets. Allocate 30 against a request for 30.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (910, 1, 1, 30.000, 2.0, 2.0);
INSERT INTO Allocations (request_id, provider_id, resource_id, quantity_allocated)
VALUES (910, 3, 1, 30.000);

SELECT 'stock_after'   AS check_name, quantity        FROM StockLevels WHERE provider_id = 3 AND resource_id = 1;
SELECT 'request_status' AS check_name, status         FROM Requests    WHERE id = 910;
SELECT 'closed_at_set'  AS check_name, closed_at IS NOT NULL FROM Requests WHERE id = 910;
SELECT 'history_rows'   AS check_name, change_type, quantity_before, quantity_after FROM StockHistory;
SELECT 'audit_rows'     AS check_name, action_type, previous_value, new_value FROM AuditLog WHERE action_type = 'stock_update';
