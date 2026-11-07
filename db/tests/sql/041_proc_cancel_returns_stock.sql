-- R8: cancelling returns every unit and keeps the allocations on record as
-- 'released' rather than deleting them.
INSERT INTO Requests (id, zone_id, resource_id, quantity_requested, severity, urgency)
VALUES (921, 1, 1, 45.000, 2.0, 2.0);
CALL sp_allocate_request(921, @a, @l, @s);
CALL sp_cancel_request(921, @released, @rlegs);

SELECT 'released_units' AS check_name, @released;
SELECT 'released_legs'  AS check_name, @rlegs;
SELECT 'stock_restored' AS check_name, provider_id, quantity
  FROM StockLevels WHERE resource_id = 1 ORDER BY provider_id;
SELECT 'allocations_kept' AS check_name, status, COUNT(*)
  FROM Allocations WHERE request_id = 921 GROUP BY status;
SELECT 'request_status' AS check_name, status FROM Requests WHERE id = 921;
